import pytest
from lab_a.sort.selection import selection
from lab_a.sort.insertion import insertion
from lab_a.sort.merge import merge, mergesort
from lab_a.sort.heap import heap
from lab_a.sort.insertion_binary import insertion_binary
from lab_a.sort.quicksort.hoare import hoare
from lab_a.sort.quicksort.hoare_last import hoare_last
from lab_a.sort.quicksort.lomuto import quick
from lab_a.sort.quicksort.median import median
from lab_a.sort.radix.buckets import buckets
from lab_a.sort.radix.counting import counting


@pytest.mark.parametrize(
    "sort_fn",
    [
        selection,
        insertion,
        mergesort,
        quick,
        # heap,
        # insertion_binary,
        # hoare,
        # hoare_last,
        #
        # median,
        # buckets,
        # counting,
    ],
)
def test_sorting_algorithms(sort_fn):
    # Note: some algorithms might modify the array in place, some might return a new one.
    # We'll check the result of the function.
    input_arr = [3, 1, 2]
    result = sort_fn(input_arr)
    # If the function returns None, we assume it's in-place and check input_arr
    actual = result if result is not None else input_arr
    assert actual == [1, 2, 3]

    input_arr = [5, 4, 3, 2, 1]
    result = sort_fn(input_arr)
    actual = result if result is not None else input_arr
    assert actual == [1, 2, 3, 4, 5]

    input_arr = []
    result = sort_fn(input_arr)
    actual = result if result is not None else input_arr
    assert actual == []

    input_arr = [5, 4, 3, 2, 1]
    result = sort_fn(input_arr)
    actual = result if result is not None else input_arr
    assert actual == [1, 2, 3, 4, 5]


#
# from lab_a.search.linear import linear
# from lab_a.search.linear_rec import linear_rec
# from lab_a.search.binary import binary
#
# def test_linear_search():
#     arr = [1, 2, 3, 4, 5]
#     assert linear(arr, 3) == 2
#     assert linear(arr, 6) == -1
#
# def test_linear_rec_search():
#     arr = [1, 2, 3, 4, 5]
#     assert linear_rec(arr, 3, 0) == 2
#     assert linear_rec(arr, 6, 0) == -1
#
# def test_binary_search():
#     arr = [1, 2, 3, 4, 5]
#     assert binary(arr, 3) == 2
#     assert binary(arr, 6) == -1
