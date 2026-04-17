def insertion(arr: list):
    for i in range(1,len(arr)):
        k = arr[i]
        j = i - 1
        while j >= 0 and k < arr[j]:
            arr[j+1] = arr[j]
            j-=1
        arr[j+1] = k
    return arr

l = [5, 2, 4, 6, 1, 3]

print(insertion(l))