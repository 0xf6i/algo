def strings(arr):
    if not arr:
        return arr

    max_len = max(len(s) for s in arr)

    for pos in range(max_len - 1, -1, -1):
        buckets = [[] for _ in range(27)]

        for s in arr:
            if pos < len(s):
                char_val = ord(s[pos].lower()) - ord("a") + 1
            else:
                char_val = 0
            buckets[char_val].append(s)

        arr = [string for bucket in buckets for string in bucket]
    return arr
