import tkinter as tk
from tkinter import ttk     # Современно выглядящие виджеты
import gostcrypto
from random import randbytes
import zlib
from PIL import Image, ImageTk

# from elements import tree_visual, folder_visual
from elements import VisualElements


def ciph():
    key = bytearray(b"Keyisimportatnpartofthisprogramm")

    text = "Веселая часть шифрования в том, что оно может не получиться.".encode("utf-8")
    text = randbytes(7)
    print(text)
    ba_text = bytearray(text)

    cipher_obj = gostcrypto.gostcipher.new('kuznechik',
                                           key,
                                           gostcrypto.gostcipher.MODE_CBC)

    cipher_text = cipher_obj.encrypt(ba_text)
    print(len(cipher_text))

    cipher_obj = gostcrypto.gostcipher.new('kuznechik',
                                           key,
                                           gostcrypto.gostcipher.MODE_CBC)

    uncipher_text = cipher_obj.decrypt(cipher_text)
    print(bytes(uncipher_text))

    aa = int.to_bytes(16, 4, 'little')
    print(aa)
    print(int.from_bytes(aa, 'little'))


def main():
    # id - par_id - child_id_list - name - is_file - file_id - deep
    # key -  0    -      1        -  2   -    3    -    4    -  5

    tree_dict = {
        '0': [None, [1, 4, 8], 'Root', 0, 0, 0],
        '1': [0, [2, 3], 'folder1', 0, 0, 1],
        '2': [1, [], 'pic1.jpg', 1, 1, 2],
        '3': [1, [], 'pic2.jpg', 1, 2, 2],
        '4': [0, [5], 'folder2', 0, 0, 1],
        '5': [4, [6], 'folder3', 0, 0, 2],
        '6': [5, [7], 'folder4', 0, 0, 3],
        '7': [6, [], 'pic3.jpg', 1, 3, 4],
        '8': [0, [], 'folder5', 0, 0, 1]
    }

    interface = VisualElements(tree_dict)

    # key = 'abcdefg'.encode('utf-8')
    # hash_obj = gostcrypto.gosthash.new('streebog256', data=key)
    # print(hash_obj.digest())









if __name__ == '__main__':
    main()