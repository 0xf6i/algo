def binary(arr, t):
    low = 0
    high = len(arr)-1

    while low <= high:
        mid = (low+high)//2
        if arr[mid] == t:
            return mid
        if arr[mid] < t:
            low = mid+1
        else:
            high = mid-1
    return -1
