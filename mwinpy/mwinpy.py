import matplotlib.pyplot as plt
import numpy as np
import time
from osgeo import gdal
from joblib import Parallel, delayed

# TODO: Documentation, thorough commenting

class MWin:
    '''
    Moving window comparison algorithm.

    Parameters
    ----------

    threads : int, default=1
        The number of cores to split the algorithm across.

    window : int, default=3
        The window size which will move across the raster map.

    '''
    def __init__(self, window_size=3, n_jobs=1):
        '''
        Initialize moving window

        Parameters
        ----------

        window_size : int, default=3
            Single integer size which indicates the i,j size of the moving
            window. E.g. window_size of 3 is equal to a window size of 3,3.
            Values must be odd numbers due to the way the window size is
            computed where the window_size // 2 is equal to the number of cells
            on each side of a cell is needed for a window.

        n_jobs : int, default=1
            Number of jobs to run in parallel across the CPU. -1 will use all
            available cores.
        '''
        self.w = window_size
        self.threads = n_jobs
        # Initialize
        self.__split_itr = []
        self.vector = []
        # Get d value which indicates the number of cells to move from the
        # original cell for the window size w.
        self.__d = window_size // 2

    def __check(self, x, y):
        if x != y:
            raise IOError

    def __split(self):
        '''
        Creates list of array position values which are used to split the array
        across the CPU.

        Returns
        -------

        iter_range : list
            List of all split cell ranges with edge artifacts taken into
            account.
        '''
        # Initial list
        iter_range = []
        # Number of splits determined by the number of threads to use.
        for j in range(self.threads):
            # Take into account edge artifacts created by loss of contextual
            # data for windows due to split.
            if j == 0:
                iter_range.append([self.__split_itr[j] - (self.cluster),
                                   self.__split_itr[j] + self.__d])
            elif j == self.threads - 1:
                iter_range.append([self.__split_itr[j] - (self.cluster +
                                  self.rem + self.__d), self.__split_itr[j]])
            else:
                iter_range.append([self.__split_itr[j] - (self.cluster +
                                  self.__d), self.__split_itr[j] + self.__d])
        return iter_range

    def __neighbors(self, arr, i, j):
        '''
        Computes neighbor vector for window size w

        Parameters
        ----------

        arr : ndarray
            Input matrix to get cell i,j neighbors

        i, j : int
            Cell location i, j

        Returns
        -------

        n : ndarray
            Cell neighborhood vector
        '''
        n = arr[i - self.__d:i + self.__d + 1,
                j - self.__d:j + self.__d + 1].flatten()
        return n

    def __mw(self, arr1, arr2, ii, j):
        '''
        Computes moving window algorithm as described by Costanza 1989.

        Parameters
        ----------

        arr1 : ndarray
            First array for comparison
        arr2 : ndarry
            Second array for comparison
        ii : int
            Cell location i
        j : int
            Cell location j

        Returns
        -------

        similarity : float
            Similarity value for cell i, j with neighborhood of window size
            'w'. Value will range between 0.0 - 1.0.
        '''

        # number of total cells across two neighborhoods with window size w.
        w = (((self.w * 2) + 1) ** 2)

        # Assign nodata value of -1 which will be ignored in final coefficient
        if arr1[ii][j] and arr2[ii][j] == self.nodata:
            return -1
        else:
            # Get neighborhood vectors of each cell i, j in arrays 1 and 2.
            a = self.__neighbors(arr1, ii, j)
            b = self.__neighbors(arr2, ii, j)
            # Find number of cells which are different values. A value of
            # 0 indicates it is the same.
            c = abs(a - b)
            d = len(np.nonzero(c)[0])
            # Divide number of cells which are different by the total number of
            # cells in the two neighborhoods. If it is 100% similar assign cell
            # the value of 1.
            similarity = abs((1 - d / w)) if d != 0 else w / w
            return similarity

    def moving_window(self, arr1, arr2):
        '''
        Moving window implementation where the number of cores utilized is one.

        Parameters
        ----------

        arr1 : ndarray
            First array for comparison
        arr2 : ndarry
            Second array for comparison

        Returns
        -------

        vector : list
            List vector which contains similarity values of each cell

        '''
        w = (((self.w * 2) + 1) ** 2)
        vector = []
        for ii in range(arr1.shape[0]):
            for j in range(arr1.shape[1]):
                vector.append(self.__mw(arr1, arr2, ii, j))
        return vector

    def split_moving_window(self, arr1, arr2, sl):
        '''
        Moving window implementation where the number of cores utilized is
        more than one.

        Parameters
        ----------

        arr1 : ndarray
            First array for comparison
        arr2 : ndarry
            Second array for comparison
        sl : list
            Section of arr1 and arr2 which has assigned to CPU core.

        Returns
        -------

        vector : list
            List vector which contains similarity values of each cell

        '''
        arr1_sl, arr2_sl = arr1[sl[1][0] : sl[1][1], ], \
                           arr2[sl[1][0] : sl[1][1], ]
        vector = []
        if sl[0] == 0:
            for ii in range(arr1_sl.shape[0] - self.__d):
                for j in range(arr1_sl.shape[1]):
                    vector.append(self.__mw(arr1_sl, arr2_sl, ii, j))

        elif sl[0] == self.threads - 1:
            for ii in range(self.__d, arr1_sl.shape[0]):
                for j in range(arr1_sl.shape[1]):
                    vector.append(self.__mw(arr1_sl, arr2_sl, ii, j))
        else:
            for ii in range(self.__d, arr1_sl.shape[0] - (self.__d)):
                for j in range(arr1_sl.shape[1]):
                    vector.append(self.__mw(arr1_sl, arr2_sl, ii, j))
        return vector

    def fit(self, x, y, nodata=None):
        '''
        Computes moving window algorithm.

        Parameters
        ----------

        x : ndarray, str
            Must be ndarray or a valid raster file path.
        y : ndarray, str
            Must be ndarray or a valid raster file path.
        nodata : int, default=None
            Only needs to be set if x and y are ndarrays, otherwise the nodata
            value is read from the raster datasets.
        '''

        if type(x) and type(y) == str:
            path1 = gdal.Open(x)
            path2 = gdal.Open(y)
            arr1 = path1.GetRasterBand(1).ReadAsArray()
            arr2 = path2.GetRasterBand(1).ReadAsArray()
            self.nodata = path1.GetRasterBand(1).GetNoDataValue()
            self.__check(self.nodata, path2.GetRasterBand(1).GetNoDataValue())
        elif type(x) and type(y) == np.ndarray:
            arr1 = x
            arr2 = y
            self.nodata = nodata
        else:
            raise TypeError("Inputs x and y must be valid file paths or numpy arrays.")

        self.i, self.j = arr1.shape
        # Create initial list of starts and stops for the split

        self.cluster = self.i // self.threads
        self.rem = self.i % self.threads

        itera = 0
        for f in range(self.threads):
            if f == self.threads - 1:
                self.__split_itr.append((self.cluster) + itera +
                                        (self.rem))
            else:
                self.__split_itr.append((self.cluster) + itera)
            itera += (self.cluster)

        if self.threads == 1:
            results = []
            results.append(self.moving_window(arr1, arr2))
        else:
            slice = self.__split()
            slice_dict = {}
            for i in range(len(slice)):
                slice_dict.update({i: slice[i]})
            results = Parallel(n_jobs=self.threads)(delayed(
                      self.split_moving_window)(arr1, arr2, sl)
                      for sl in slice_dict.items())

        vector = []
        for i in range(len(results)):
            vector += results[i]
        vector_arr = np.array(vector)

        tw = sum(1 for n in vector if n != -1)
        self.sim = np.sum(vector_arr) / (tw)

        mat = vector_arr.reshape([self.i, self.j])
        self.matrix = np.ma.masked_where(mat == -1,
                                    mat,
                                    copy=True)


        return results

    def plot(self, cmap="Greys"):

        plt.imshow(self.matrix, cmap=cmap)
        plt.show()

if __name__ == '__main__':
    # arr1 = np.random.randint(2, size=(753, 200))
    # arr2 = np.random.randint(2, size=(753, 200))
    x = "/home/owen/Data/mwin/2016.tif"
    y = "/home/owen/Data/mwin/2013.tif"

    w = [3, 13, 23, 33, 43, 53, 63]
    t = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    out_dict = {}
    out_times = []

    t = 3
    w = 5

    # t = int(input("Threads: "))
    # w = int(input("Window: "))
    start = time.time()
    mw = MWin(t, w)
    test = mw.fit(x, y)
    end = time.time() - start
    print(mw.sim)
    mw.plot(cmap="magma")

