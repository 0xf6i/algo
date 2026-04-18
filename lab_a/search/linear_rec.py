def linear_rec(arr, t, i):
    if len(arr) <= i:
        return -1
    if arr[i] == t:
        return i
    return linear_rec(arr, t, i + 1)
