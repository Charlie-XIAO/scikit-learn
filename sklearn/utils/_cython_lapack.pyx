from cython cimport floating

from scipy.linalg.cython_lapack cimport spotrf, dpotrf


###################################
# LAPACK Positive definite matrix #
###################################

cdef void _potrf(bint lower, int n, floating *A,
                 int lda, int *info):
    """A := L in A = L.L^T if lower, or A := U in A = U^T.U otherwise

    Note that A should be F-contiguous, e.g. cdef floating[::1, :] A
    """
    cdef:
        int i, j
        char *UPLO = "L" if lower else "U"
    if floating is float:
        spotrf(UPLO, &n, <float *> A, &lda, info)
    else:
        dpotrf(UPLO, &n, <double *> A, &lda, info)
    if lower:
        for i in range(n):
            for j in range(i + 1, n):
                A[j * n + i] = 0.
    else:
        for i in range(n):
            for j in range(i + 1, n):
                A[i * n + j] = 0.
