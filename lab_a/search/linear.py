def linear(arr, t):
    for i in range(len(arr)):
        if arr[i] == t:
            return i
    return -1