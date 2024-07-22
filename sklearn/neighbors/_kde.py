"""
Kernel Density Estimation
-------------------------
"""

# Author: Jake Vanderplas <jakevdp@cs.washington.edu>
import itertools
from numbers import Integral, Real

import numpy as np
from scipy.linalg import cholesky, solve_triangular
from scipy.special import gammainc

from ..base import BaseEstimator, _fit_context
from ..neighbors._base import VALID_METRICS
from ..utils import check_random_state
from ..utils._param_validation import Interval, StrOptions
from ..utils.extmath import row_norms
from ..utils.validation import _check_sample_weight, check_is_fitted
from ._ball_tree import BallTree
from ._kd_tree import KDTree

VALID_KERNELS = [
    "gaussian",
    "tophat",
    "epanechnikov",
    "exponential",
    "linear",
    "cosine",
]

TREE_DICT = {"ball_tree": BallTree, "kd_tree": KDTree}


# TODO: implement a brute force version for testing purposes
# TODO: create a density estimation base class?
class KernelDensity(BaseEstimator):
    """Kernel Density Estimation.

    Read more in the :ref:`User Guide <kernel_density>`.

    Parameters
    ----------
    bandwidth : float or {"scott", "silverman"}, default=1.0
        The bandwidth of the kernel. If bandwidth is a float, it defines the
        bandwidth of the kernel. If bandwidth is a string, one of the estimation
        methods is implemented.

    algorithm : {'kd_tree', 'ball_tree', 'auto'}, default='auto'
        The tree algorithm to use.

    kernel : {'gaussian', 'tophat', 'epanechnikov', 'exponential', 'linear', \
                 'cosine'}, default='gaussian'
        The kernel to use.

    metric : str, default='euclidean'
        Metric to use for distance computation. See the
        documentation of `scipy.spatial.distance
        <https://docs.scipy.org/doc/scipy/reference/spatial.distance.html>`_ and
        the metrics listed in
        :class:`~sklearn.metrics.pairwise.distance_metrics` for valid metric
        values.

        Not all metrics are valid with all algorithms: refer to the
        documentation of :class:`BallTree` and :class:`KDTree`. Note that the
        normalization of the density output is correct only for the Euclidean
        distance metric.

    atol : float, default=0
        The desired absolute tolerance of the result.  A larger tolerance will
        generally lead to faster execution.

    rtol : float, default=0
        The desired relative tolerance of the result.  A larger tolerance will
        generally lead to faster execution.

    breadth_first : bool, default=True
        If true (default), use a breadth-first approach to the problem.
        Otherwise use a depth-first approach.

    leaf_size : int, default=40
        Specify the leaf size of the underlying tree.  See :class:`BallTree`
        or :class:`KDTree` for details.

    metric_params : dict, default=None
        Additional parameters to be passed to the tree for use with the
        metric.  For more information, see the documentation of
        :class:`BallTree` or :class:`KDTree`.

    Attributes
    ----------
    n_features_in_ : int
        Number of features seen during :term:`fit`.

        .. versionadded:: 0.24

    tree_ : ``BinaryTree`` instance
        The tree algorithm for fast generalized N-point problems.

    feature_names_in_ : ndarray of shape (`n_features_in_`,)
        Names of features seen during :term:`fit`. Defined only when `X`
        has feature names that are all strings.

    bandwidth_ : float
        Value of the bandwidth, given directly by the bandwidth parameter or
        estimated using the 'scott' or 'silverman' method.

        .. versionadded:: 1.0

    See Also
    --------
    sklearn.neighbors.KDTree : K-dimensional tree for fast generalized N-point
        problems.
    sklearn.neighbors.BallTree : Ball tree for fast generalized N-point
        problems.

    Examples
    --------
    Compute a gaussian kernel density estimate with a fixed bandwidth.

    >>> from sklearn.neighbors import KernelDensity
    >>> import numpy as np
    >>> rng = np.random.RandomState(42)
    >>> X = rng.random_sample((100, 3))
    >>> kde = KernelDensity(kernel='gaussian', bandwidth=0.5).fit(X)
    >>> log_density = kde.score_samples(X[:3])
    >>> log_density
    array([-0.36399292,  0.03333733, -0.28804462])
    """

    _parameter_constraints: dict = {
        "bandwidth": [
            Interval(Real, 0, None, closed="neither"),
            StrOptions({"scott", "silverman"}),
        ],
        "algorithm": [StrOptions(set(TREE_DICT.keys()) | {"auto"})],
        "kernel": [StrOptions(set(VALID_KERNELS))],
        "metric": [
            StrOptions(
                set(itertools.chain(*[VALID_METRICS[alg] for alg in TREE_DICT.keys()]))
            )
        ],
        "atol": [Interval(Real, 0, None, closed="left")],
        "rtol": [Interval(Real, 0, None, closed="left")],
        "breadth_first": ["boolean"],
        "leaf_size": [Interval(Integral, 1, None, closed="left")],
        "metric_params": [None, dict],
    }

    def __init__(
        self,
        *,
        bandwidth=1.0,
        algorithm="auto",
        kernel="gaussian",
        metric="euclidean",
        atol=0,
        rtol=0,
        breadth_first=True,
        leaf_size=40,
        metric_params=None,
    ):
        self.algorithm = algorithm
        self.bandwidth = bandwidth
        self.kernel = kernel
        self.metric = metric
        self.atol = atol
        self.rtol = rtol
        self.breadth_first = breadth_first
        self.leaf_size = leaf_size
        self.metric_params = metric_params

    def _choose_algorithm(self, algorithm, metric):
        # given the algorithm string + metric string, choose the optimal
        # algorithm to compute the result.
        if algorithm == "auto":
            # use KD Tree if possible
            if metric in KDTree.valid_metrics:
                return "kd_tree"
            elif metric in BallTree.valid_metrics:
                return "ball_tree"
        else:  # kd_tree or ball_tree
            if metric not in TREE_DICT[algorithm].valid_metrics:
                raise ValueError(
                    "invalid metric for {0}: '{1}'".format(TREE_DICT[algorithm], metric)
                )
            return algorithm

    @_fit_context(
        # KernelDensity.metric is not validated yet
        prefer_skip_nested_validation=False
    )
    def fit(self, X, y=None, sample_weight=None):
        """Fit the Kernel Density model on the data.

        Parameters
        ----------
        X : array-like of shape (n_samples, n_features)
            List of n_features-dimensional data points.  Each row
            corresponds to a single data point.

        y : None
            Ignored. This parameter exists only for compatibility with
            :class:`~sklearn.pipeline.Pipeline`.

        sample_weight : array-like of shape (n_samples,), default=None
            List of sample weights attached to the data X.

            .. versionadded:: 0.20

        Returns
        -------
        self : object
            Returns the instance itself.
        """
        algorithm = self._choose_algorithm(self.algorithm, self.metric)

        if sample_weight is not None:
            sample_weight = _check_sample_weight(
                sample_weight, X, dtype=np.float64, only_non_negative=True
            )
            normalized_sample_weight = sample_weight / sample_weight.sum()
            n_effective_samples = 1 / np.sum(normalized_sample_weight**2)
        else:
            n_effective_samples = X.shape[0]

        if isinstance(self.bandwidth, str):
            if self.bandwidth == "scott":
                self.bandwidth_ = n_effective_samples ** (-1 / (X.shape[1] + 4))
            elif self.bandwidth == "silverman":
                self.bandwidth_ = (n_effective_samples * (X.shape[1] + 2) / 4) ** (
                    -1 / (X.shape[1] + 4)
                )
        else:
            self.bandwidth_ = self.bandwidth

        X = self._validate_data(X, order="C", dtype=np.float64)

        if X.shape[0] == 1:
            raise ValueError(
                "n_samples=1 while KernelDensity requires more than one sample"
            )

        # The formula is:
        #   1 / (N * sum(w_i) * |H|) * sum_i [ w_i * K(H^{-1} (x - x_i)) ],
        # where H = bandwidth * covariance^{1/2}. Here `self._cho_cov` is just the
        # square root of the covariance matrix
        self._cov = np.atleast_2d(np.cov(X.T, aweights=sample_weight))
        self._cho_cov = cholesky(self._cov, lower=True)

        kwargs = self.metric_params
        if kwargs is None:
            kwargs = {}

        # Data need to be scaled before passing to the tree (bandwidth is taken care
        # of by the tree so we only scale by covariance^{-1/2} here)
        self.tree_ = TREE_DICT[algorithm](
            solve_triangular(self._cho_cov, X.T, lower=True).T,
            metric=self.metric,
            leaf_size=self.leaf_size,
            sample_weight=sample_weight,
            **kwargs,
        )
        return self

    def score_samples(self, X):
        """Compute the log-likelihood of each sample under the model.

        Parameters
        ----------
        X : array-like of shape (n_samples, n_features)
            An array of points to query.  Last dimension should match dimension
            of training data (n_features).

        Returns
        -------
        density : ndarray of shape (n_samples,)
            Log-likelihood of each sample in `X`. These are normalized to be
            probability densities, so values will be low for high-dimensional
            data.
        """
        check_is_fitted(self)
        # The returned density is normalized to the number of points.
        # For it to be a probability, we must scale it.  For this reason
        # we'll also scale atol.
        X = self._validate_data(X, order="C", dtype=np.float64, reset=False)
        if self.tree_.sample_weight is None:
            N = self.tree_.data.shape[0]
        else:
            N = self.tree_.sum_weight
        atol_N = self.atol * N

        # Points need to be scaled in the same way as tree data
        log_density = self.tree_.kernel_density(
            solve_triangular(self._cho_cov, X.T, lower=True).T,
            h=self.bandwidth_,
            kernel=self.kernel,
            atol=atol_N,
            rtol=self.rtol,
            breadth_first=self.breadth_first,
            return_log=True,
        )

        # The result of self.tree_.kernel_density is only normalized by
        # the kernel norm and bandwidth. We need to further normalize by
        # the determinant of the square root of the covariance matrix and N
        log_density -= np.log(N) + np.sum(np.log(np.diag(self._cho_cov)))
        return log_density

    def score(self, X, y=None):
        """Compute the total log-likelihood under the model.

        Parameters
        ----------
        X : array-like of shape (n_samples, n_features)
            List of n_features-dimensional data points.  Each row
            corresponds to a single data point.

        y : None
            Ignored. This parameter exists only for compatibility with
            :class:`~sklearn.pipeline.Pipeline`.

        Returns
        -------
        logprob : float
            Total log-likelihood of the data in X. This is normalized to be a
            probability density, so the value will be low for high-dimensional
            data.
        """
        return np.sum(self.score_samples(X))

    def sample(self, n_samples=1, random_state=None):
        """Generate random samples from the model.

        Currently, this is implemented only for gaussian and tophat kernels.

        Parameters
        ----------
        n_samples : int, default=1
            Number of samples to generate.

        random_state : int, RandomState instance or None, default=None
            Determines random number generation used to generate
            random samples. Pass an int for reproducible results
            across multiple function calls.
            See :term:`Glossary <random_state>`.

        Returns
        -------
        X : array-like of shape (n_samples, n_features)
            List of samples.
        """
        check_is_fitted(self)
        # TODO: implement sampling for other valid kernel shapes
        if self.kernel not in ["gaussian", "tophat"]:
            raise NotImplementedError()

        # Tree data is already scaled at creation, need to convert back
        data = np.dot(np.asarray(self.tree_.data), self._cho_cov.T)

        rng = check_random_state(random_state)
        u = rng.uniform(0, 1, size=n_samples)
        if self.tree_.sample_weight is None:
            i = (u * data.shape[0]).astype(np.int64)
        else:
            cumsum_weight = np.cumsum(np.asarray(self.tree_.sample_weight))
            sum_weight = cumsum_weight[-1]
            i = np.searchsorted(cumsum_weight, u * sum_weight)

        if self.kernel == "gaussian":
            norm = rng.multivariate_normal(
                np.zeros(data.shape[1]),
                self._cov * self.bandwidth_**2,
                size=n_samples,
            )
            return np.atleast_2d(data[i] + norm)

        elif self.kernel == "tophat":
            # we first draw points from a d-dimensional normal distribution,
            # then use an incomplete gamma function to map them to a uniform
            # d-dimensional tophat distribution.
            dim = data.shape[1]
            X = rng.normal(size=(n_samples, dim))
            s_sq = row_norms(X, squared=True)
            correction = (
                gammainc(0.5 * dim, 0.5 * s_sq) ** (1.0 / dim)
                * self.bandwidth_
                / np.sqrt(s_sq)
            )
            return data[i] + X * correction[:, np.newaxis]

    def _more_tags(self):
        return {
            "_xfail_checks": {
                "check_sample_weights_invariance": (
                    "sample_weight must have positive values"
                ),
            }
        }
