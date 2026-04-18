def hoare_last(arr, low, hi):
    if low < hi:
        p = partition(arr, low, hi)
        hoare_last(arr, low, p)
        hoare_last(arr, p + 1, hi)


def partition(arr, low, hi):
    pivot = arr[hi]
    i = low - 1
    j = hi + 1

    while True:
        i += 1
        while arr[i] < pivot:
            i += 1
        j -= 1
        while arr[j] > pivot:
            j -= 1

        if i >= j:
            return j if j < hi else j - 1
        arr[i], arr[j] = arr[j], arr[i]
