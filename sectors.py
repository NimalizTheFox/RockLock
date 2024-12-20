import os
import gostcrypto
import json


class Sector:
    """Класс сектора, предназначен для корректной работы с ФС"""
    def __init__(self, num_sector, file_path, key, sector_size=4096):
        self.sector_size = sector_size      # 4Кб размер одного и каждого сектора
        self.sector_number = num_sector     # Номер сектора по порядку
        self.file_path = file_path          # Путь до шифрованной ФС
        self.first_byte_address = self.sector_size * self.sector_number     # Адрес первого байта сектора
        self.key = key                      # Ключ шифрования

        # Вектор инициализации для каждого сектора - хэш от его номера
        self.init_vect = gostcrypto.gosthash.new(
            'streebog256', data=int.to_bytes(self.sector_number, 4, 'little')
        ).digest()[:32]

    def read_sector(self) -> bytes:
        """Расшифровка и чтение сектора"""
        with open(self.file_path, 'rb') as file:
            file.seek(self.first_byte_address, os.SEEK_SET)
            data = file.read(self.sector_size)

            cipher_obj = gostcrypto.gostcipher.new('kuznechik',
                                                   self.key,
                                                   gostcrypto.gostcipher.MODE_CBC,
                                                   init_vect=self.init_vect)
        return bytes(cipher_obj.decrypt(bytearray(data)))

    def write_sector(self, data: bytes) -> None:
        """Шифровка и запись data в свой сектор"""
        len_to_add = self.sector_size - len(data)
        data += b'\x00' * len_to_add   # Добивка до полного сектора

        # Создание объекта шифровки
        cipher_obj = gostcrypto.gostcipher.new('kuznechik',
                                               self.key,
                                               gostcrypto.gostcipher.MODE_CBC,
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


class FirstSector:
    """Класс первого сектора, предназначен для работы с заголовками"""
    def __init__(self, key, file_path, sector_size=4096):
        self.key = key                  # Ключ шифрования
        self.file_path = file_path      # Путь до файла ФС
        self.sector_size = sector_size  # Размер одного сектора
        self.head_key = bytes(gostcrypto.gosthash.new('streebog512', data=bytearray(self.key)).digest())

    def create_new(self) -> None:
        """Создание нового сектора заголовков"""
        # Хэш для проверки корректности введенного ключа
        data = self.head_key

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
        Sector(0, self.file_path, self.key, self.sector_size).write_sector(data)

    def read_sector(self) -> tuple:
        """Полная информация заголовков"""
        data = Sector(0, self.file_path, self.key, self.sector_size).read_sector()  # Собсна чтение сектора
        head_key = data[:64]    # Получение строки подтверждения ключа

        len_stot = int.from_bytes(data[64:68], 'little')    # Длина таблицы секторов дерева деревьев
        sectors_tot = json_decode(data[68: 68 + len_stot])  # таблица секторов дерева деревьев

        sectors = sectors_tot['tree_of_trees_sectors']      # Собсна сами сектора
        data = b''                                          # И чтение данных заново для получения полной таблицы дд
        for i in sectors:
            data += Sector(i, self.file_path, self.key, self.sector_size).read_sector()

        len_tot = int.from_bytes(data[68 + len_stot:68 + len_stot + 4], 'little')           # Длина дерева деревьев
        tree_of_trees = json_decode(data[68 + len_stot + 4: 68 + len_stot + 4 + len_tot])   # Само дерево деревьев
        return head_key, sectors_tot, tree_of_trees

    def read_sectors_tot(self) -> dict:
        """Чтение таблицы с секторами, в которых располагается дерево деревьев"""
        data = Sector(0, self.file_path, self.key, self.sector_size).read_sector()
        len_stot = int.from_bytes(data[64:68], 'little')
        return json_decode(data[68: 68 + len_stot])

    def read_tot(self) -> dict:
        """Чтение дерева деревьев с соответствующих секторов"""
        sectors = self.read_sectors_tot()['tree_of_trees_sectors']  # Узнаем сектора, читаем из них данные
        data = b''
        for i in sectors:
            data += Sector(i, self.file_path, self.key, self.sector_size).read_sector()

        # И преобразуем в таблицу
        len_stot = int.from_bytes(data[64:68], 'little')
        len_tot = int.from_bytes(data[68 + len_stot:68 + len_stot + 4], 'little')
        return json_decode(data[68 + len_stot + 4: 68 + len_stot + 4 + len_tot])

    def update_sectors_tot(self, new_sections_tot: dict) -> None:
        """Изменение записанной таблицы секторов дерева деревьев"""
        tree_of_trees = self.read_tot()     # Читаем уже записанное дерево деревьев, чтобы перезаписать на новое место
        data = self.head_key

        dict_stot = json_encode(new_sections_tot)
        len_stot = len(dict_stot)
        data += int.to_bytes(len_stot, 4, 'little') + dict_stot

        dict_tot = json_encode(tree_of_trees)
        len_tot = len(dict_tot)
        data += int.to_bytes(len_tot, 4, 'little') + dict_tot

        # Запись данных в несколько секторов
        for i in range(len(new_sections_tot)):
            Sector(new_sections_tot[i], self.file_path, self.key, self.sector_size).write_sector(
                data[i * self.sector_size: (i + 1) * self.sector_size]
            )

    def update_tree_of_trees(self, new_tree_of_trees: dict) -> None:
        """Обновление дерева деревьев"""
        sectors_tot = self.read_sectors_tot()
        data = self.head_key

        dict_stot = json_encode(sectors_tot)
        len_stot = len(dict_stot)
        data += int.to_bytes(len_stot, 4, 'little') + dict_stot

        dict_tot = json_encode(new_tree_of_trees)
        len_tot = len(dict_tot)
        data += int.to_bytes(len_tot, 4, 'little') + dict_tot

        # Если текущий размер заголовков превышает размер сектор, то создается новый с занесением в таблицу
        if len(data) > len(sectors_tot) * self.sector_size:
            sectors_tot['tree_of_trees_sectors'].append(os.path.getsize(self.file_path)//self.sector_size)
            self.update_sectors_tot(sectors_tot)            # Запоминаем новый сектор
            self.update_tree_of_trees(new_tree_of_trees)    # Запускаем функцию заново
        else:
            # Иначе просто записываем в сектора данные
            for i in range(len(sectors_tot['tree_of_trees_sectors'])):
                Sector(sectors_tot[i], self.file_path, self.key, self.sector_size).write_sector(
                    data[i * self.sector_size: (i + 1) * self.sector_size]
                )


class TableSector:
    """Класс секторов с таблицами/заголовками"""
    def __init__(self, key, file_path, table_name: str, sector_size=4096):
        self.key = key
        self.file_path = file_path
        self.sector_size = sector_size

        if table_name not in ['tree', 'file', 'free']:  # Возможные имена таблиц
            raise Exception('Нет такой таблицы!')
        else:
            self.table_name = table_name
        self.sectors_name = f'{self.table_name}_table_sectors'  # Сектора этих таблиц

    def create_new_table(self) -> None:
        """Создание новой таблицы"""
        # Получаем сектора для записи новой таблицы
        sectors = FirstSector(self.key, self.file_path, self.sector_size).read_tot()[self.sectors_name]

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
            Sector(sectors[i], self.file_path, self.key, self.sector_size).write_sector(
                data[i * self.sector_size: (i + 1) * self.sector_size]
            )

    def update_table(self, new_table: dict) -> None:
        """Обновление таблицы, перезапись секторов новой таблицей"""
        sectors = FirstSector(self.key, self.file_path, self.sector_size).read_tot()[self.sectors_name]
        dict_table = json_encode(new_table)
        len_table = len(dict_table)
        data = int.to_bytes(len_table, 4, 'little') + dict_table

        if len(data) > len(sectors) * self.sector_size:
            sector_0 = FirstSector(self.key, self.file_path, self.sector_size)  # Объект нулевого сектора

            tree_of_trees = sector_0.read_tot()             # Читаем таблицу распределения секторов
            # Добавляем новый сектор в таблицу распределения секторов
            tree_of_trees[self.sectors_name].append(os.path.getsize(self.file_path)//self.sector_size)

            sector_0.update_tree_of_trees(tree_of_trees)    # И записываем обновленную таблицу секторов
            sectors = tree_of_trees[self.sectors_name]      # Обновляем уже имеющуюся информацию по секторам

        # Запись по секторам
        for i in range(len(sectors)):
            Sector(sectors[i], self.file_path, self.key, self.sector_size).write_sector(
                data[i * self.sector_size: (i + 1) * self.sector_size]
            )

    def read_table(self) -> dict:
        """Чтение таблицы"""
        sectors = FirstSector(self.key, self.file_path, self.sector_size).read_tot()[self.sectors_name]
        data = b''
        for i in sectors:
            data += Sector(i, self.file_path, self.key, self.sector_size).read_sector()

        len_table = int.from_bytes(data[:4], 'little')
        table = json_decode(data[4: 4 + len_table])
        return table


class FileSector:
    """Класс файловых секторов"""
    def __init__(self, key, file_path, sector_size=4096):
        self.key = key
        self.file_path = file_path
        self.sector_size = sector_size

    def write_file(self, new_file_path, parent_id) -> None:
        """Получаем название файла и заносим его в ФС"""
        with open(new_file_path, 'rb') as file:     # Читаем файл
            file_data = file.read()

        # Превращаем в данные для ФС
        len_file = len(file_data)
        data = int.to_bytes(len_file, 4, 'little') + file_data

        # Открываем сразу все заголовки
        free_table_sectors = TableSector(self.key, self.file_path, 'free', self.sector_size)
        file_table_sectors = TableSector(self.key, self.file_path, 'file', self.sector_size)
        tree_table_sectors = TableSector(self.key, self.file_path, 'tree', self.sector_size)

        free_sectors = free_table_sectors.read_table()['free']
        file_dict = file_table_sectors.read_table()
        tree_dict = tree_table_sectors.read_table()

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
            Sector(sectors[i], self.file_path, self.key, self.sector_size).write_sector(
                data[i * self.sector_size: (i + 1) * self.sector_size]
            )

        # Обновление всех заголовков
        file_dict[file_id] = [sectors, file_name]   # Заносим в таблицу файлов сектора и изначальное имя файла
        file_table_sectors.update_table(file_dict)

        tree_id = str(int(list(tree_dict.keys())[-1]) + 1)
        tree_dict[tree_id] = [int(parent_id), [], file_name, 1, file_id, tree_dict[str(parent_id)][5] + 1]
        tree_table_sectors.update_table(tree_dict)

        free_table_sectors.update_table({'free': free_sectors})

    def read_file(self, file_id) -> None:
        """Чтение и запуск файла"""
        file_table = TableSector(self.key, self.file_path, 'file', self.sector_size).read_table()[str(file_id)]
        sectors = file_table[0]
        file_name = file_table[1]

        data = b''
        for i in sectors:
            data += Sector(i, self.file_path, self.key, self.sector_size).read_sector()

        file_len = int.from_bytes(data[:4], 'little')
        file_data = data[4: 4 + file_len]

        # Проверяем есть ли папка для файлов
        if not os.path.exists('C:\\Program Files\\RockLock'):
            os.mkdir('C:\\Program Files\\RockLock')     # Если нет, то создаем

        with open(f'C:\\Program Files\\RockLock\\{file_name}', 'wb') as f:
            f.write(file_data)  # Пишем в эту папку расшифрованный файл

        os.system(f'attrib +h "C:\\Program Files\\RockLock\\{file_name}"')  # Говорим файлу, что он скрытый
        os.startfile(f'C:\\Program Files\\RockLock\\{file_name}')           # И запускаем

    def delete_file(self, file_id) -> None:
        """Удаление файла из ФС"""
        # Открываем таблички файлов и свободных секторов (из таблицы иерархии удаление происходит в интерфейсе)
        free_table_sectors = TableSector(self.key, self.file_path, 'free', self.sector_size)
        file_table_sectors = TableSector(self.key, self.file_path, 'file', self.sector_size)

        free_sectors = free_table_sectors.read_table()['free']
        file_dict = file_table_sectors.read_table()

        # Секторы, занимаемые файлом
        sectors = file_dict[str(file_id)][0]

        # Удаляем ноду с файлом из таблицы файлов
        del file_dict[str(file_id)]

        # Сразу записываем сектора файла как свободные
        free_sectors += sectors
        free_table_sectors.update_table({'free': free_sectors})

        # И зануляем их
        for i in sectors:
            Sector(i, self.file_path, self.key, self.sector_size).write_sector(b'')


def main():
    filename = 'purum.txt'
    key = 'purum'.encode('utf-8')
    key_h = gostcrypto.gosthash.new('streebog256', data=key).digest()

    tree = {
        '0': [None, [1, 4, 8], 'Root', 0, 0, 0],
        '1': [0, [2, 3], 'folder1', 0, 0, 1],
        '2': [1, [], 'pic1.jpg', 1, 1, 2],
        '3': [1, [], 'pic2.jpg', 1, 2, 2],
        '4': [0, [5], 'folder2', 0, 0, 1],
        '5': [4, [6], 'folder3', 0, 0, 2],
        '6': [5, [7], 'folder4', 0, 0, 3],
        '7': [6, [], 'pic3.jpg', 1, 3, 4],
        '8': [0, [], 'folder4', 0, 0, 1]
    }

    sector_0 = FirstSector(key_h, filename)
    sector_0.create_new()
    print(sector_0.read_sector())

    Sector(1, filename, key_h).write_sector(b'hello')
    print(Sector(1, filename, key_h).read_sector())
    print(FirstSector(key_h, filename).read_sector())













if __name__ == '__main__':
    main()