def lomuto(arr, low, hi):
    if low >= hi or low < 0:
        return
    p = partition(arr, low, hi)
    lomuto(arr, low, p - 1)
    lomuto(arr, p + 1, hi)


def partition(arr, low, hi):
    pivot = arr[hi]
    i = low

    for j in range(low, hi):
        if arr[j] <= pivot:
            arr[i], arr[j] = arr[j], arr[i]
            i = i + 1
    arr[i], arr[hi] = arr[hi], arr[i]
    return i
