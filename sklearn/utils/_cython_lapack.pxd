from cython cimport floating


# LAPACK Positive definite matrix #############################################

cdef void _potrf(bint, int, floating *, int, int *)
