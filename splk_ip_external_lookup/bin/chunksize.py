import time
sample_list = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
chunked_list = list()
chunk_size = 3
for i in range(0, len(sample_list), chunk_size):
    chunked_list.append(sample_list[i:i+chunk_size])
print(chunked_list)
print(int(time.time()))
print(int(time.localtime()))