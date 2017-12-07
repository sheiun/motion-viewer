from functools import reduce
from PIL import Image
import multiprocessing
import threading
import logging
import scipy
from graphviz import Digraph
from scipy import ndimage

import numpy as np

LOCAL_MINIMA_TOLERANCE = 1E-2
SAME_MOTION_SIMILARITY_TOL = (0.1, 0.3)
DIFF_MOTION_SIMILARITY_TOL = (0.0, 0.3)

def normalize_np_matrix(mat):
  min_value = np.nanmin(mat)
  max_value = np.nanmax(mat)

  elem_wise_operation = np.vectorize(lambda x : 1.0 if x != x else ((x - min_value) / (max_value - min_value)))
  return elem_wise_operation(mat)

def from_matrix_to_image(mat, normalize = False, border = (0, 0)):
    if normalize:
        mat = normalize_np_matrix(mat, border)

    #im = Image.new("RGB", mat.shape)
    #data = [(int(mat[x, y] * 255), int(mat[x, y] * 255), int(mat[x, y] * 255)) for y in range(im.size[1]) for x in range(im.size[0])]
    #im.putdata(data)

    #return im
    return Image.fromarray((mat * 255).astype('uint8'), "L")

def gradient_magnitude(gx, gy):
    out = np.empty(gx.shape, dtype=np.float32)
    for i in range(gx.shape[0]):
      for j in range(gx.shape[1]):
          out[i, j] = math.sqrt(math.pow(gx[i, j], 2) + math.pow(gy[i, j], 2))

    return out


class MotionGraph:
	class Edge:
		def __init__(self, src, dst, motion, frames):
			self._src = src
			self._dst = dst
			self._motion = motion
			self._frames = frames

	class Node:
		def __init__(self, motion):
			self.label = ''
			self.motion = motion
			self.out = []


    INVALID_DISTANCE = float("nan")

    def __init__(self, window_length):
        self._motions = []
        self._similarity_mat = None

        if window_length is None or window_length <= 0:
            raise RuntimeError("Window length must be an integer value greater than zero.")

        self._window_length = window_length
        self._nodes = []

    def add_motion(self, motion):
        """ Adds a new motion in the motion graph.
        Since the motion graph construction is time consuming,
        the correct way to used this API is by adding all motions firstly,
        followed by calling build.

        Args:
            motion (AnimatedSkeleton): motion data
        """

        self._motions.append(motion)

    def build(self):
        """ This function creates the motion graph using all motion data
        previously added by calling the function add_motion.

        Notes:
            TODO: Handle more than one motion:
        """
        import cProfile, pstats, io
        pr = cProfile.Profile()
        pr.enable()

        self._build_similarity_matrix()
        self._find_local_minima()

        pr.disable()
        s = io.StringIO()
        sortby = 'time'
        ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        ps.print_stats()
        print(s.getvalue())

    def _build_similarity_matrix(self):
        self._build_list_of_poses()

        num_frames = self.num_frames
        self._similarity_mat = np.empty([num_frames, num_frames], dtype=np.float32)

        # Compute the distance between each pair of frame
        for i in range(num_frames):
            print("[DEBUG] (Build MotionGraph {}/{} - ({:.3f})%".format(i, num_frames - 1, i/(num_frames-1) * 100))
            for j in range(num_frames):
                self._similarity_mat[i, j] = self._difference_between_frames(i, j)

        shape = (0, len(self._motions[0]), 0, len(self._motions[0]))
        self._similarity_mat[shape[0]:shape[1], shape[2]:shape[3]] = normalize_np_matrix(self._similarity_mat[shape[0]:shape[1], shape[2]:shape[3]])

        shape = (len(self._motions[0]), self._similarity_mat.shape[0], 0, len(self._motions[0]))
        self._similarity_mat[shape[0]:shape[1], shape[2]:shape[3]] = normalize_np_matrix(self._similarity_mat[shape[0]:shape[1], shape[2]:shape[3]])

        shape = (0, len(self._motions[0]), len(self._motions[0]), self._similarity_mat.shape[1])
        self._similarity_mat[shape[0]:shape[1], shape[2]:shape[3]] = normalize_np_matrix(self._similarity_mat[shape[0]:shape[1], shape[2]:shape[3]])

        shape = (len(self._motions[0]), self._similarity_mat.shape[0], len(self._motions[0]), self._similarity_mat.shape[1])
        self._similarity_mat[shape[0]:shape[1], shape[2]:shape[3]] = normalize_np_matrix(self._similarity_mat[shape[0]:shape[1], shape[2]:shape[3]])

        #self._similarity_mat = normalize_np_matrix(self._similarity_mat)

    def _find_local_minima(self):
        # Compute the gradient of the similarity matrix
        gx, gy = np.gradient(self._similarity_mat)
        gradient_mat = gradient_magnitude(gx, gy)

        np.savetxt("./mat.log", gradient_mat, fmt='%1.4f')

        all_minima = []
        all_minimum_pixels = np.zeros(gradient_mat.shape)
        for i in range(gradient_mat.shape[0]):
            for j in range(gradient_mat.shape[1]):
                TOLERANCE = DIFF_MOTION_SIMILARITY_TOL

                if self._motion_data_containing_frame(i) ==\
                   self._motion_data_containing_frame(j):
                  TOLERANCE = SAME_MOTION_SIMILARITY_TOL

                if gradient_mat[i, j] < LOCAL_MINIMA_TOLERANCE:
                      all_minima.append((i, j, self._similarity_mat[i, j]))
                      if self._similarity_mat[i, j] >= TOLERANCE[0] and self._similarity_mat[i,j] <= TOLERANCE[1]:
                          all_minimum_pixels[i, j] = 1.0
        #            all_minima_img_pixels[i * self.num_frames + j] = (255, 0, 0)
        #        #else:
        #        #    local_minima_img[i,j] = (grad_image[i, j], grad_image[i, j], grad_image[i, j])

        Image.fromarray((all_minimum_pixels * 255).astype('uint8'), "L").show()

        # Normalizes the distance values and convertes from distance to 
        # similarity (basically similatiry = 1 - distance)
        #min_value = np.nanmin(self._similarity_mat)
        #max_value = np.nanmax(self._similarity_mat)

        #elem_wise_operation = np.vectorize(lambda x : 1.0 if x != x else ((x - min_value) / (max_value - min_value)))
        #self._similarity_mat = elem_wise_operation(self._similarity_mat)
        norm = normalize_np_matrix(self._similarity_mat)
        Image.fromarray((norm * 400).astype('uint8'), "L").save("test.png")

        #local_minima_img.save("f:\\local_minima.png")
        #from_matrix_to_image(gx).save("f:\\gx.png")
        #from_matrix_to_image(gy).save("f:\\gy.png")
        #from_matrix_to_image(gradient_mat, True).save("f:\\mag.png")
        #from_matrix_to_image(new_grad, True, (self._window_length, self._window_length)).save("f:\\mag2.png")
        from_matrix_to_image(self._similarity_mat, False).save("similarity.png")

    @property
    def num_frames(self):
        #import ipdb; ipdb.set_trace()
        #summation_func = lambda x, y: len(x) + len(y)
        #return reduce(summation_func, self._motions, [])
        count = 0
        for motion in self._motions:
            count += len(motion)
        return count

    def get_similarity_matrix_as_image(self):
        """ Builds a greyscale image using the similarity matrix data.

        Returns:
            Returns the greyscale image (PIL.Image)

        Notes:
             This function can only be called after building the MotionGraph. Otherwise,
             a RuntimeError will be raised.
        """

        if self._similarity_mat is None:
            raise RuntimeError("MotionGraph.get_similarity_matrix_as_image function can only be called after " +\
                               "calling MotionGraph.build function.")

        return self._motion_graph_image()

    def save_similarity_mat_as_txt_file(self, fn):
        """ Saves the similarity matrix in text file.

        Notes:
             This function can only be called after building the MotionGraph. Otherwise,
             a RuntimeError will be raised.
        """

        if self._similarity_mat is None:
            raise RuntimeError("MotionGraph.save_similarity_mat_as_txt_file function can only be called after " +\
                               "calling MotionGraph.build function.")

        np.savetxt(fn, self._similarity_mat, fmt='%1.4f')

    def _difference_between_frames(self, i, j):
        ## Clamp window size to shortest possible. It is important to handle poses at the beginning
        ## and at the end of the animation
        #win_length = self._window_length
        #if (i + win_length) > (self.num_frames - 1) or (j - win_length) < 0:
        #       win_length = min(self.num_frames - i, j + 1)

        window_i = self._motion_window(i, i + self._window_length - 1)
        window_j = self._motion_window(j - (self._window_length - 1), j)
        #window_i = self._motion_window(i, i + win_length - 1)
        #window_j = self._motion_window(j - (win_length- 1), j)

        if window_i is None or window_j is None:
            return MotionGraph.INVALID_DISTANCE

        if len(window_i) != len(window_j):
            raise RuntimeError("Distance metric can only be computed for motion windows " +\
                               "with the same length.")

        # Computes the distance between the two windows
        diff_vec = window_i - window_j
        return np.linalg.norm(diff_vec)

    def _motion_window(self, begin_frame, end_frame):
        """ Returns the interval of motion frames given the first and last
        interface indices.

        Args:
            begin_frame (int): index first window frame
            end_frame   (int): index last window frame

        Note:
            All provided indices must be defined considering that all added motions' frames are
            stored as an unique list. In orther words, the first frame of the second will be numbered
            as the last frame of the first motion + 1.

            None will be returned if the given window indices are not valid. To be
            considered as valid, the begin and last window frames must belong to the same
            motion path.
        """

        # Check if the provided indices are valid
        if begin_frame < 0 or end_frame >= self.num_frames:
            return None

        # Check if the whole window lies in the same motion clip
        motion = self._motion_data_containing_frame(begin_frame)
        if motion != self._motion_data_containing_frame(end_frame):
            return None

        if motion is None:
            raise RuntimeError("Invalid motion returned for the given frame index.")

        return self._frames_pose[begin_frame : end_frame + 1, ]

    def _motion_data_containing_frame(self, frame_idx):
        """ Returns the motion data related to the given global frame index."""

        local_idx = frame_idx

        for motion in self._motions:
            if local_idx < len(motion):
                return motion
            else:
                local_idx -= len(motion)

        raise RuntimeError("Could not find the motion graph related to the given frame index ({}).".format(frame_idx))

    def _motion_graph_image(self):
        pillow_compatible = (self._similarity_mat * 255).astype('uint8')
        return Image.fromarray(pillow_compatible, "L")

    def _build_list_of_poses(self):
        first_motion = self._motion_data_containing_frame(0)
        pose_dimensions = len(first_motion.get_all_joint_rotations(0)[0])

        self._frames_pose = np.empty((self.num_frames, pose_dimensions), dtype=np.float32)

        offset = 0
        for motion in self._motions:
            for i in range(len(motion)):
                self._frames_pose[offset + i:] = motion.get_all_joint_rotations(i)[0]

            offset += len(motion)

    def _motion_frame_number(self, motion, gframe):
    	for cur in self._motions:
    		if cur == self._motions:
    			return gframe
    		gframe -= cur.num_frames

    def _graph_find_frame(self, motion, frame):
    	for node in self._nodes:
    		if node.motion == motion:
    			cur = node
    			while True:
    				for out_edge in cur.out:
    					if out_edge.motion == motion:
    						if frame < out_edge.frames[-1]:
    							return out_edge
    						cur = out_edge
    						break

    def _graph_export_graphviz(self):
    	dot = Digraph(comment='Motion Graph')

    	# We like recursive..
    	def _export_node_rec(node):
    		dot.node(id(node), node.label)
    		for out_edge in node.out:
    			dot.edge([id(out_edge.src), id(out_edge.dst)])
				_export_node_rec(out_edge.dst)

    	for node in self._nodes:
    		_export_node_rec(node)

    	# dot.render() ??? TODO


    # self._local_minima = np.array((NUM_MINIMA, 2))
    def _generate_graph(self):
    	self._nodes.clear()	

    	# Creating one transition for each input motion
     	for motion in self._motions:
     		motion_beg = Node(motion)
     		motion_end = Node(motion)
     		transition = Edge(motion_beg, motion_end, motion, np.arange(motion.num_frames))
     		motion_beg.out.append(transition)
     		self._nodes.append(motion_beg)

     	# Insert transitions between motions for each local minima 
     	for minima in self._local_minima:
     		gsrc, gdst = minima
     		src_motion = self._motion_data_containing_frame(gsrc)
     		dst_motion = self._motion_data_containing_frame(gdst)

     		# Getting frame idx relative to motion path
     		src = self._motion_frame_number(src_motion, gsrc)
     		dst = self._motion_frame_number(dst_motion, gdst)

     		if src_motion is None:
            	raise RuntimeError("Invalid motion returned for the given frame index.")

            src_edge = self._graph_find_frame(src_motion, src)
            dst_edge = self._graph_find_frame(dst_motion, dst)
			
			# New split nodes
			new_src_node = Node(src_motion)
            new_dst_node = Node(dst_motion)
            
            transition = Edge(new_src_node, new_dst_node, None, [0]) # TODO Syntesize new frames!!

         	# Creating and inserting new transition
            src_edge.src.out.remove(src_edge)
            # dst_edge.dst.in.remove(src_edge)

            # Creating 4 new edges
            # B-------->E ~ B--(new_src_edge0)-->(new_src_node)--(new_src_edge1)-->E
            new_src_edge0 = Edge(src_edge.src, new_src_node)
            new_src_edge1 = Edge(new_src_node, src_edge.dst)
            new_dst_edge0 = Edge(dst_edge.src, new_dst_node)
            new_dst_edge1 = Edge(new_dst_node, dst_edge.dst)

            # Adding edges to respective nodes
            src_edge.src.out.append(new_src_edge0)
            dst_edge.src.out.append(new_dst_edge0)
            new_src_node.out.append(new_src_edge1)
            new_dst_node.out.append(new_dst_edge1)


        # Prune graph

        # Export
        self._graph_export_graphviz()


if __name__ == "__main__":
    from skeleton import *
    logging.basicConfig(level=logging.DEBUG)
    motion0 = AnimatedSkeleton()
    motion0.load_from_file("data\\02\\02_02.bvh")
    motion1 = AnimatedSkeleton()
    motion1.load_from_file("data\\02\\02_03.bvh")

    graph = MotionGraph(30)
    graph.add_motion(motion0)
    graph.add_motion(motion1)

    import time
    start = time.time()
    graph.build()
    print('It took {0:0.1f} seconds'.format(time.time() - start))
    graph.get_similarity_matrix_as_image().show()