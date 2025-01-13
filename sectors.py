import os
import gostcrypto
import json
import tkinter as tk
from tkinter import ttk


def create_key(byte_string):
    """Создание ключа для кузнечика"""
    return gostcrypto.gosthash.new('streebog256', data=byte_string).digest()


class Sector:
    """Класс сектора, предназначен для корректной работы с ФС"""
    def __init__(self, num_sector, file_path, key, sector_size, cipher, cipher_method):
        self.sector_size = sector_size      # Размер каждого сектора
        self.sector_number = num_sector     # Номер сектора по порядку
        self.file_path = file_path          # Путь до шифрованной ФС
        self.first_byte_address = self.sector_size * self.sector_number     # Адрес первого байта сектора
        self.key = key                      # Ключ шифрования
        self.cipher = cipher                # Шифр и метод шифрования
        self.cipher_method = gostcrypto.gostcipher.MODE_ECB if cipher_method == 'ECB' \
            else gostcrypto.gostcipher.MODE_CBC

        # Вектор инициализации для каждого сектора - хэш от его номера
        self.init_vect = gostcrypto.gosthash.new(
            'streebog256', data=int.to_bytes(self.sector_number, 4, 'little')
        ).digest()[:32]

    def read_sector(self) -> bytes:
        """Расшифровка и чтение сектора"""
        with open(self.file_path, 'rb') as file:
            file.seek(self.first_byte_address, os.SEEK_SET)
            data = file.read(self.sector_size)
            cipher_obj = gostcrypto.gostcipher.new(self.cipher,
                                                   self.key,
                                                   self.cipher_method,
                                                   init_vect=self.init_vect)
        return bytes(cipher_obj.decrypt(bytearray(data)))

    def write_sector(self, data: bytes) -> None:
        """Шифровка и запись data в свой сектор"""
        len_to_add = self.sector_size - len(data)
        data += b'\x00' * len_to_add   # Добивка до полного сектора

        # Создание объекта шифровки
        cipher_obj = gostcrypto.gostcipher.new(self.cipher,
                                               self.key,
                                               self.cipher_method,
                                               init_vect=self.init_vect)
        enc_data = cipher_obj.encrypt(bytearray(data))  # Собсна шифрование

        with open(self.file_path, 'r+b') as file:   # 'r+b', так как при 'wb' файл полностью стирается перед записью
            file.seek(self.first_byte_address)      # Переход к началу сектора в файле
            file.write(enc_data)


def json_encode(json_dict: dict) -> bytes:
    """Преобразование табличных данных в байты"""
    return json.dumps(json_dict, separators=(',', ':')).encode('utf-8')


def json_decode(json_bytes: bytes) -> dict:
    """Преобразование из байтов в табличные данные"""
    return json.loads(json_bytes)


def list_compress(data_list: list) -> list:
    """Сжимаем список секторов: [1, 2, 3, 4] -> [(1,4)]"""
    if len(data_list) > 0:
        data_list.sort()
        first_num = data_list[0]    # Первый номер
        cont_num = first_num        # Продолжающийся номер
        new_data = []               # Результат сжатия
        for i in data_list[1:]:     # Проходимся по всему списку
            if i - cont_num == 1:   # Если элемент - продолжение предыдущего, то продолжаем
                cont_num += 1
            else:                   # Иначе записываем в новый список
                if first_num == cont_num:       # Если это одиночный элемент, то пишем только его
                    new_data.append(first_num)
                else:                           # Если это диапазон, то пишем в tuple
                    new_data.append([first_num, cont_num])
                first_num = i       # И начинаем снова
                cont_num = first_num
        if first_num == cont_num:   # Не забываем записать последний проход
            new_data.append(first_num)
        else:
            new_data.append((first_num, cont_num))
    else:
        new_data = []
    return new_data


def list_decompress(data_list: list) -> list:
    """Разворачиваем список"""
    new_data = []
    for i in data_list:
        if type(i) is list:
            new_data += [j for j in range(i[0], i[1] + 1)]
        else:
            new_data.append(i)
    new_data.sort()
    return new_data


class FirstSector:
    """Класс первого сектора, предназначен для работы с заголовками"""
    def __init__(self, key, file_path, sector_size, cipher, sipher_method):
        self.key = key                  # Ключ шифрования
        self.file_path = file_path      # Путь до файла ФС
        self.sector_size = sector_size  # Размер одного сектора
        self.head_key = bytes(gostcrypto.gosthash.new('streebog512', data=bytearray(self.key)).digest())

        # Жестко зафиксированы шифр и метод,
        # так как до расшифровки мы не знаем какой из них нам нужен, а они нужны для расшифровки
        self.cipher = 'kuznechik'
        self.cipher_method = 'CBC'

        self.fs_cipher = cipher
        self.fs_cipher_method = sipher_method

    def create_new(self) -> None:
        """Создание нового сектора заголовков"""
        # Хэш для проверки корректности введенного ключа
        data = self.head_key
        data += int.to_bytes(self.sector_size, 2, 'little')
        data += int.to_bytes(0 if self.fs_cipher == 'magma' else 1, 1, 'little')
        data += int.to_bytes(0 if self.fs_cipher_method == 'ECB' else 1, 1, 'little')

        # Секторы заголовка
        sectors_tot = {
            'tree_of_trees_sectors': [0]
        }

        # Дерево деревьев или сектора остальных таблиц
        tree_of_trees = {
            'tree_table_sectors': [1],  # Таблица иерархического дерева
            'file_table_sectors': [2],  # Таблица файлов
            'free_table_sectors': [3]   # Таблицы свободных секторов
        }

        # Процедура сохранения таблицы в свой сектор
        json_stot = json_encode(sectors_tot)
        len_stot = len(json_stot)
        data += int.to_bytes(len_stot, 4, 'little') + json_stot

        json_tot = json_encode(tree_of_trees)
        len_tot = len(json_tot)
        data += int.to_bytes(len_tot, 4, 'little') + json_tot

        # Так как я точно знаю что заголовки займут меньше одного сектора я сохраняю его в нулевой сектор
        Sector(0, self.file_path, self.key, self.sector_size, self.cipher, self.cipher_method).write_sector(data)

    def read_sector(self) -> tuple:
        """Информация для точности расшифровки"""
        data = Sector(0, self.file_path, self.key, 1024, self.cipher, self.cipher_method
                      ).read_sector()   # Чтение сектора
        head_key = data[:64]            # Получение строки подтверждения ключа
        self.sector_size = int.from_bytes(data[64:66], 'little')        # Получение размера сектора

        cipher_byte = int.from_bytes(data[66:67], 'little')
        cipher = 'magma' if cipher_byte == 0 else 'kuznechik'           # Определяем шифр ФС

        cipher_method_byte = int.from_bytes(data[67:68], 'little')
        cipher_method = 'ECB' if cipher_method_byte == 0 else 'CBC'     # Определяем метод шифрования
        return head_key, self.sector_size, cipher, cipher_method

    def read_sectors_tot(self) -> dict:
        """Чтение таблицы с секторами, в которых располагается дерево деревьев"""
        data = Sector(0, self.file_path, self.key, self.sector_size, self.cipher, self.cipher_method).read_sector()
        len_stot = int.from_bytes(data[68:72], 'little')
        return json_decode(data[72: 72 + len_stot])

    def read_tot(self) -> dict:
        """Чтение дерева деревьев с соответствующих секторов"""
        sectors = self.read_sectors_tot()['tree_of_trees_sectors']  # Узнаем сектора, читаем из них данные
        data = b''
        for i in sectors:
            data += Sector(i, self.file_path, self.key, self.sector_size, self.cipher, self.cipher_method).read_sector()

        # И преобразуем в таблицу
        len_stot = int.from_bytes(data[68:72], 'little')
        len_tot = int.from_bytes(data[72 + len_stot:72 + len_stot + 4], 'little')
        return json_decode(data[72 + len_stot + 4: 72 + len_stot + 4 + len_tot])

    def update_sectors_tot(self, new_sections_tot: dict) -> None:
        """Изменение записанной таблицы секторов дерева деревьев"""
        tree_of_trees = self.read_tot()     # Читаем уже записанное дерево деревьев, чтобы перезаписать на новое место
        data = self.head_key
        data += int.to_bytes(self.sector_size, 2, 'little')
        data += int.to_bytes(0 if self.fs_cipher == 'magma' else 1, 1, 'little')
        data += int.to_bytes(0 if self.fs_cipher_method == 'ECB' else 1, 1, 'little')

        dict_stot = json_encode(new_sections_tot)
        len_stot = len(dict_stot)
        data += int.to_bytes(len_stot, 4, 'little') + dict_stot

        dict_tot = json_encode(tree_of_trees)
        len_tot = len(dict_tot)
        data += int.to_bytes(len_tot, 4, 'little') + dict_tot

        # Запись данных в несколько секторов
        for i in range(len(new_sections_tot)):
            Sector(new_sections_tot[i], self.file_path, self.key, self.sector_size, self.cipher, self.cipher_method
                   ).write_sector(data[i * self.sector_size: (i + 1) * self.sector_size])

    def update_tree_of_trees(self, new_tree_of_trees: dict) -> None:
        """Обновление дерева деревьев"""
        sectors_tot = self.read_sectors_tot()
        data = self.head_key
        data += int.to_bytes(self.sector_size, 2, 'little')
        data += int.to_bytes(0 if self.fs_cipher == 'magma' else 1, 1, 'little')
        data += int.to_bytes(0 if self.fs_cipher_method == 'ECB' else 1, 1, 'little')

        dict_stot = json_encode(sectors_tot)
        len_stot = len(dict_stot)
        data += int.to_bytes(len_stot, 4, 'little') + dict_stot

        dict_tot = json_encode(new_tree_of_trees)
        len_tot = len(dict_tot)
        data += int.to_bytes(len_tot, 4, 'little') + dict_tot

        # Если текущий размер заголовков превышает размер сектор, то создается новый с занесением в таблицу
        if len(data) > (len(sectors_tot) * self.sector_size):
            sectors_tot['tree_of_trees_sectors'].append(os.path.getsize(self.file_path)//self.sector_size)
            self.update_sectors_tot(sectors_tot)            # Запоминаем новый сектор
            self.update_tree_of_trees(new_tree_of_trees)    # Запускаем функцию заново
        else:
            # Иначе просто записываем в сектора данные
            for i in range(len(sectors_tot['tree_of_trees_sectors'])):
                Sector(sectors_tot['tree_of_trees_sectors'][i], self.file_path, self.key,
                       self.sector_size, self.cipher, self.cipher_method
                       ).write_sector(data[i * self.sector_size: (i + 1) * self.sector_size])


class TableSector:
    """Класс секторов с таблицами/заголовками"""
    def __init__(self, key, file_path, table_name: str, sector_size, cipher, cipher_method):
        self.key = key
        self.file_path = file_path
        self.sector_size = sector_size
        self.cipher = cipher
        self.cipher_method = cipher_method

        if table_name not in ['tree', 'file', 'free']:  # Возможные имена таблиц
            raise Exception('Нет такой таблицы!')
        else:
            self.table_name = table_name
        self.sectors_name = f'{self.table_name}_table_sectors'  # Сектора этих таблиц

    def create_new_table(self) -> None:
        """Создание новой таблицы"""
        # Получаем сектора для записи новой таблицы
        sectors = FirstSector(self.key, self.file_path, self.sector_size, self.cipher, self.cipher_method
                              ).read_tot()[self.sectors_name]

        # У каждой таблицы своя структура
        if self.table_name == 'tree':
            # 'id': [parent_id, [childes_id_list], 'name', is_file, file_id, deep], deep - глубина в иерархии
            table = {'0': [None, [], 'Root', 0, 0, 0]}
        elif self.table_name == 'file':
            # 'id': [[sectors], первоначальное_имя]
            table = {}
        else:
            # 'free': [sectors]
            table = {'free': []}

        # Данные это длина таблицы и сама таблица
        dict_table = json_encode(table)
        len_table = len(dict_table)
        data = int.to_bytes(len_table, 4, 'little') + dict_table

        # Запись по секторам
        for i in range(len(sectors)):
            Sector(sectors[i], self.file_path, self.key, self.sector_size, self.cipher, self.cipher_method
                   ).write_sector(data[i * self.sector_size: (i + 1) * self.sector_size])

    def update_table(self, new_table: dict) -> None:
        """Обновление таблицы, перезапись секторов новой таблицей"""
        sectors = FirstSector(self.key, self.file_path, self.sector_size, self.cipher, self.cipher_method
                              ).read_tot()[self.sectors_name]
        dict_table = json_encode(new_table)
        len_table = len(dict_table)
        data = int.to_bytes(len_table, 4, 'little') + dict_table

        if len(data) > (len(sectors) * self.sector_size):
            # Объект нулевого сектора
            sector_0 = FirstSector(self.key, self.file_path, self.sector_size, self.cipher, self.cipher_method)

            tree_of_trees = sector_0.read_tot()             # Читаем таблицу распределения секторов
            # Добавляем новый сектор в таблицу распределения секторов
            tree_of_trees[self.sectors_name].append(os.path.getsize(self.file_path)//self.sector_size)

            sector_0.update_tree_of_trees(tree_of_trees)    # И записываем обновленную таблицу секторов
            self.update_table(new_table)
        else:
            # Запись по секторам
            for i in range(len(sectors)):
                Sector(sectors[i], self.file_path, self.key, self.sector_size, self.cipher, self.cipher_method
                       ).write_sector(data[i * self.sector_size: (i + 1) * self.sector_size])

    def read_table(self) -> dict:
        """Чтение таблицы"""
        sectors = FirstSector(self.key, self.file_path, self.sector_size, self.cipher, self.cipher_method
                              ).read_tot()[self.sectors_name]
        data = b''
        for i in sectors:
            data += Sector(i, self.file_path, self.key, self.sector_size, self.cipher, self.cipher_method
                           ).read_sector()

        len_table = int.from_bytes(data[:4], 'little')
        table = json_decode(data[4: 4 + len_table])
        return table


class FileSector:
    """Класс файловых секторов"""
    def __init__(self, key, file_path, sector_size, cipher, cipher_method):
        self.key = key
        self.file_path = file_path
        self.sector_size = sector_size
        self.cipher = cipher
        self.cipher_method = cipher_method

    def write_file(self, new_file_path: str, progressbar: ttk.Progressbar, frame: tk.Frame) -> tuple[int, str]:
        """Получаем название файла и заносим его в ФС, возвращает id файла"""
        with open(new_file_path, 'rb') as file:     # Читаем файл
            file_data = file.read()

        # TODO: Переделать под многопоточную запись файла в ФС

        # Превращаем в данные для ФС
        len_file = len(file_data)
        data = int.to_bytes(len_file, 4, 'little') + file_data

        # Открываем сразу все заголовки
        free_table_sectors = TableSector(self.key, self.file_path, 'free',
                                         self.sector_size, self.cipher, self.cipher_method)
        file_table_sectors = TableSector(self.key, self.file_path, 'file',
                                         self.sector_size, self.cipher, self.cipher_method)

        free_sectors = list_decompress(free_table_sectors.read_table()['free'])
        file_dict = file_table_sectors.read_table()

        # Если этой первый файл, то нужно его записать со всеми почестями!
        if len(file_dict) > 0:
            file_id = str(int(list(file_dict.keys())[-1]) + 1)
        else:
            file_id = '0'

        # Вычисляем имя файла вне зависимости от направления слэша (господи, мне нужен сон)
        file_name = new_file_path[
                    (new_file_path.rfind('\\') if new_file_path.find('\\') > 0
                     else new_file_path.rfind('/')) + 1:]

        # Определение того, какие сектора займет файл в базе
        num_sectors = (len(data) + self.sector_size - 1) // self.sector_size    # Сколько секторов нужно файлу

        progressbar['maximum'] = float(num_sectors)
        frame.update()

        if len(free_sectors) >= num_sectors:    # Если свободных секторов больше чем требуемых, то просто пишем в них
            sectors = free_sectors[:num_sectors]
            free_sectors = free_sectors[num_sectors:]
        else:   # Иначе записываем в то что есть и создаем недостающие сектора, обнуляем таблицу пустых секторов
            init_sector = os.path.getsize(self.file_path) // self.sector_size   # Первый сектор для записи
            num_sectors -= len(free_sectors)
            sectors = free_sectors + [i for i in range(init_sector, init_sector + num_sectors)]
            free_sectors = []

        # Запись в базу по секторам
        for i in range(len(sectors)):
            Sector(sectors[i], self.file_path, self.key, self.sector_size, self.cipher, self.cipher_method
                   ).write_sector(data[i * self.sector_size: (i + 1) * self.sector_size])

            progressbar['value'] = float(i)
            frame.update()

        progressbar['value'] = float(num_sectors)
        frame.update()

        # Заносим в таблицу файлов сектора и изначальное имя файла
        file_dict[file_id] = [file_name, list_compress(sectors)]
        file_table_sectors.update_table(file_dict)  # Обновляем таблицу

        free_table_sectors.update_table({'free': list_compress(free_sectors)})
        return int(file_id), file_name

    def read_file(self, file_id, progressbar: ttk.Progressbar, frame: ttk.Frame) -> tuple[str, bytes]:
        """Простое чтение файла, возвращает имя файла и его байты"""
        file_table = TableSector(self.key, self.file_path, 'file', self.sector_size, self.cipher, self.cipher_method
                                 ).read_table()[str(file_id)]
        file_name, sectors = file_table
        sectors = list_decompress(sectors)

        progressbar['maximum'] = float(len(sectors))
        frame.update()

        data = b''
        for i in range(len(sectors)):
            data += Sector(sectors[i], self.file_path, self.key, self.sector_size, self.cipher, self.cipher_method
                           ).read_sector()

            progressbar['value'] = float(i)
            frame.update()

        file_len = int.from_bytes(data[:4], 'little')
        file_data = data[4: 4 + file_len]
        return file_name, file_data

    def exec_file(self, file_id, progressbar: ttk.Progressbar, frame: ttk.Frame) -> None:
        """Чтение и запуск файла"""
        file_table = TableSector(self.key, self.file_path, 'file', self.sector_size, self.cipher, self.cipher_method
                                 ).read_table()[str(file_id)]
        file_name, sectors = file_table
        sectors = list_decompress(sectors)

        # Расшифрованные для запуска файлы храним в аппдате
        app_directory = os.path.expanduser("~") + '\\AppData\\Local\\RockLock'

        progressbar['maximum'] = float(len(sectors))
        frame.update()

        if os.path.exists(f'{app_directory}\\{file_name}'):     # Если файл уже распакован, то просто
            progressbar['value'] = float(100)
            frame.update()

            os.startfile(f'{app_directory}\\{file_name}')       # Запускаем
        else:                                                   # Если нет, то распаковываем
            data = b''

            for i in range(len(sectors)):
                data += Sector(sectors[i], self.file_path, self.key, self.sector_size, self.cipher, self.cipher_method
                               ).read_sector()

                progressbar['value'] = float(i)
                frame.update()

            file_len = int.from_bytes(data[:4], 'little')
            file_data = data[4: 4 + file_len]

            # Проверяем есть ли папка для файлов
            if not os.path.exists(app_directory):
                os.mkdir(app_directory)     # Если нет, то создаем

            with open(f'{app_directory}\\{file_name}', 'wb') as f:
                f.write(file_data)  # Пишем в эту папку расшифрованный файл

            os.system(f'attrib +h "{app_directory}\\{file_name}"')  # Говорим файлу, что он скрытый
            os.startfile(f'{app_directory}\\{file_name}')           # И запускаем

    def delete_file(self, file_id) -> None:
        """Удаление файла из ФС"""
        # Открываем таблички файлов и свободных секторов (из таблицы иерархии удаление происходит в интерфейсе)
        free_table_sectors = TableSector(self.key, self.file_path, 'free',
                                         self.sector_size, self.cipher, self.cipher_method)
        file_table_sectors = TableSector(self.key, self.file_path, 'file',
                                         self.sector_size, self.cipher, self.cipher_method)

        free_sectors = list_decompress(free_table_sectors.read_table()['free'])
        file_dict = file_table_sectors.read_table()

        # Секторы, занимаемые файлом
        sectors = list_decompress(file_dict[str(file_id)][1])

        del file_dict[str(file_id)]                 # Удаляем ноду с файлом из таблицы файлов
        file_table_sectors.update_table(file_dict)  # И обновляем таблицу файлов в файле

        # Сразу записываем сектора файла как свободные
        free_sectors += sectors
        free_table_sectors.update_table({'free': list_compress(free_sectors)})
        # И не зануляем, т.к. это долго


def main():
    filename = r'C:\Users\NIMALIZ\Desktop\NewFileSystem.rlfs'
    key = '1234'.encode('utf-8')
    key_h = create_key(key)

    sector_0 = FirstSector(key_h, filename, 1024, '', '')
    print(sector_0.read_sector())
    print(sector_0.read_sectors_tot())
    print(sector_0.read_tot())

    _, sector_size, cipher, cipher_method = sector_0.read_sector()

    file_table = TableSector(key_h, filename, 'file', sector_size, cipher, cipher_method).read_table()
    for key in file_table:
        print(key, file_table[key])

    print('\n' * 2)

    tree_table = TableSector(key_h, filename, 'tree', sector_size, cipher, cipher_method).read_table()
    for key in tree_table:
        print(key, tree_table[key])

    print('\n' * 2)

    free_table = TableSector(key_h, filename, 'free', sector_size, cipher, cipher_method).read_table()
    print(free_table)


if __name__ == '__main__':
    main()
