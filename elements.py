from tkinter.messagebox import askyesno, showerror
from tkinter import filedialog, font
from PIL import Image, ImageTk
import copy
import sys
from sectors import *


def resource_path(relative_path):
    """Для корректного отображения картинок в режиме --one-file"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class VisualElements:
    """Класс визуальных элементов или интерфейса"""
    def __init__(self):
        self.columns = 4            # Количество колонок файлов во фрейме папок

        # Рандомные переменные
        self.is_looping = False
        self.key = b''
        self.file_path = ''
        self.tree_dict = {}
        self.sector_size = 4096
        self.tree_sector = TableSector('', '', 'tree')

        # Собсна интерфейс
        self.root = tk.Tk()
        self.root.title("RockLock")
        self.root.geometry("800x600+560+240")
        self.root.resizable(False, False)
        self.root.option_add("*tearOff", tk.FALSE)  # Чтоб не было пунктира в пунктах меню
        self.root.iconbitmap(default=resource_path('RockLock.ico'))

        # Картинки файла и папки разных размеров
        mini_ico_size = 14
        self.maxi_ico_size = 80
        self.image_folder_mini = ImageTk.PhotoImage(Image.open(resource_path('folder_ico.png')).resize((mini_ico_size, mini_ico_size)))
        self.image_folder_maxi = ImageTk.PhotoImage(Image.open(resource_path('folder_ico.png')).resize((self.maxi_ico_size, self.maxi_ico_size)))
        self.image_file_mini = ImageTk.PhotoImage(Image.open(resource_path('file_ico.png')).resize((mini_ico_size, mini_ico_size)))
        self.image_file_maxi = ImageTk.PhotoImage(Image.open(resource_path('file_ico.png')).resize((self.maxi_ico_size, self.maxi_ico_size)))

        # Главное меню
        main_menu = tk.Menu()
        main_menu.add_command(label="Создать", command=lambda: self.create_new_file_system())
        main_menu.add_command(label="Открыть", command=lambda: self.open_file_system())
        self.root.config(menu=main_menu)

        # Немного стиля
        label_style = ttk.Style()
        label_style.configure("TFrame", background='white')  # фоновый цвет
        label_style.configure("TLabel", background='white')  # фоновый цвет

        # Фрейм для прогрессбаров
        self.status_frame = ttk.Frame(self.root, height=40, style='TFrame', borderwidth=0, relief=tk.GROOVE)
        self.status_frame.pack(side=tk.BOTTOM, anchor=tk.E, fill=tk.X)
        self.status_frame.grid_columnconfigure(0, weight=1)
        self.status_frame.grid_columnconfigure(1, weight=1)

        # Фрейм для иерархического дерева
        self.tree_frame = ttk.Frame(master=self.root, borderwidth=0, relief=tk.GROOVE)
        self.tree_frame.pack(side=tk.LEFT, anchor=tk.N, fill=tk.Y, pady=3, padx=2)

        self.tree = ttk.Treeview(master=self.tree_frame)
        self.tree.heading("#0", text='RockLock Explorer', anchor=tk.NW)
        self.tree.pack(expand=1, fill=tk.BOTH)

        # Фрейм для отображения папок и файлов, плюс настройка скроллбара (да, это сложно)
        frame_canvas = ttk.Frame(master=self.root)
        frame_canvas.pack(side=tk.LEFT, anchor=tk.N, fill=tk.BOTH, expand=1)
        frame_canvas.grid_rowconfigure(0, weight=1)
        frame_canvas.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(frame_canvas, background='white', borderwidth=2, relief=tk.GROOVE)
        self.scrollbar = ttk.Scrollbar(frame_canvas, orient=tk.VERTICAL, command=self.canvas.yview)

        self.folders_frame = ttk.Frame(self.canvas)
        self.folders_frame.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.folders_frame, anchor=tk.N, width=560)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollbar.grid(row=0, column=1, sticky=tk.NS)
        self.canvas.grid(row=0, column=0, sticky=tk.NSEW)

        self.canvas.bind_all("<MouseWheel>", self._on_mouse_wheel, add='+')

        def context_menu_folder_frame(event):
            """Контекстное меню (по нажатию ПКМ) для правой области"""
            parent_id = self.tree.selection()[0]    # Узнаем в какой папке это нужно сделать
            menu = tk.Menu(tearoff=0)               # Убираем пунктирную линию
            menu.add_command(label='Создать папку', command=lambda: self.node_create(event, parent_id))
            menu.add_separator()
            menu.add_command(label='Загрузить файл', command=lambda: self.node_file_load(event, parent_id))
            menu.add_command(label='Загрузить папку', command=lambda: self.node_folder_load(event, parent_id))
            menu.post(event.x_root, event.y_root)

        self.canvas.bind('<Button-3>', context_menu_folder_frame)
        self.folders_frame.bind('<Button-3>', context_menu_folder_frame)

        self.root.mainloop()

    def _on_mouse_wheel(self, event):
        """Прокрутка вверх/вниз в зависимости от направления колеса"""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def update_scrollbar(self, num_elements):
        """Проверяем количество строк и активируем или отключаем скроллбар"""
        if num_elements > self.columns * 4:
            self.scrollbar.grid(row=0, column=1, sticky=tk.NS)
            self.canvas.configure(yscrollcommand=self.scrollbar.set)
        else:
            self.scrollbar.grid_forget()
            self.canvas.configure(yscrollcommand="")

    def create_new_file_system(self):
        """Создание новой ФС"""
        window = tk.Toplevel()
        window.title("Создание новой ФС")
        window.geometry('600x400+660+340')  # Появление в центре экрана (для FHD экранов)
        window.resizable(False, False)
        window.protocol("WM_DELETE_WINDOW", lambda: dismiss())  # перехватываем нажатие на крестик

        # Для красивого отображения
        pad_y = 6
        pad_x = 15

        for i in range(3):
            window.grid_columnconfigure(i, weight=1)
        window.grid_columnconfigure(1, weight=2)
        for i in range(10):
            window.grid_rowconfigure(i, weight=1)

        # Просто заголовок
        ttk.Label(window,
                  text='Создание файла, в котором будет создана\nновая зашифрованная файловая система.',
                  background='grey94', font=font.Font(size=12, underline=True), justify=tk.RIGHT
                  ).grid(row=0, column=0, columnspan=3, pady=20, padx=15)

        # Выбор места
        ttk.Label(window,
                  text='Нажмите на кнопку и выберите файл',
                  background='grey94'
                  ).grid(row=1, column=0, columnspan=3, sticky=tk.W, padx=pad_x, pady=pad_y)

        # Для отображения пути выбранного файла
        path_label = ttk.Label(window,
                               text='',
                               background='white',
                               relief=tk.GROOVE)
        path_label.grid(row=2, column=0, columnspan=2, sticky=tk.EW, padx=pad_x, pady=pad_y, ipadx=2, ipady=2)

        # Сам выбор файла
        ttk.Button(window, text='Обзор...', command=lambda: create_file()).grid(row=2, column=2, sticky=tk.EW, padx=15)

        ttk.Label(window,
                  text='Выберите количество байт в одном секторе',
                  background='grey94'
                  ).grid(row=3, column=0, columnspan=2, sticky=tk.E, padx=pad_x, pady=pad_y)

        # Поле для размера сектора
        sector_size_entry = ttk.Entry(window)
        sector_size_entry.insert(0, '1024')
        sector_size_entry.grid(row=3, column=2, sticky=tk.EW, padx=15)

        # Ли-и-и-и-иния
        ttk.Separator(window, orient=tk.HORIZONTAL).grid(row=4, column=0, columnspan=3, sticky=tk.EW, pady=12, padx=10)

        # Выбор метода шифрования (ключ и\или файл)
        key_value = tk.IntVar(window)
        file_value = tk.IntVar(window)

        ttk.Label(window,
                  text='Выберите метод создания ключа (можно выбрать оба)',
                  background='grey94'
                  ).grid(row=5, column=0, columnspan=3, sticky=tk.EW, padx=pad_x, pady=pad_y)

        # Галочка для пароля
        check_key = ttk.Checkbutton(window, text='Пароль:', variable=key_value)
        check_key.grid(row=6, column=0, sticky=tk.E, padx=pad_x, pady=pad_y)

        # Поле для ввода пароля
        check_key_entry = ttk.Entry(window)
        check_key_entry.grid(row=6, column=1, columnspan=2, sticky=tk.EW, padx=pad_x)

        # Галочка для контрольного файла
        check_file_path = tk.StringVar()
        check_file = ttk.Checkbutton(window, text='    Файл:', variable=file_value)
        check_file.grid(row=7, column=0, sticky=tk.E, padx=pad_x, pady=pad_y)

        check_file_label = ttk.Label(window,
                                     textvariable=check_file_path,
                                     background='white',
                                     relief=tk.GROOVE)
        check_file_label.grid(row=7, column=1, columnspan=2, sticky=tk.EW, padx=pad_x, pady=pad_y, ipadx=2, ipady=2)

        ttk.Button(window, text='Обзор...', command=lambda: open_check_file()
                   ).grid(row=8, column=2, sticky=tk.EW, padx=pad_x)

        # Можно считать, что это невидимый разделитель между основной частью и завершающими кнопками
        tk.Frame(window).grid(row=9, column=0, columnspan=3, pady=12)

        ttk.Button(window, text="Подтвердить", command=lambda: create_fs()
                   ).grid(row=10, column=0, padx=pad_x, pady=15, sticky=tk.W)
        ttk.Button(window, text="Отмена", command=lambda: dismiss()
                   ).grid(row=10, column=2, padx=pad_x, pady=15, sticky=tk.E)

        window.grab_set()   # Говорим что это приоритетное окно
        # То есть пока его не закрыть к основному окну доступ не получить

        def create_fs():
            """Создание новой ФС при подтверждении"""
            # Проверки разные
            if self.file_path != '':
                with open(self.file_path, 'wb') as file:
                    file.write(b'')
            else:
                showerror('Нет файла ФС', 'Пожалуйста, выберите файл для новой файловой системы')
                return None

            key_byte_string = b''
            if key_value.get() == 1:
                if check_key_entry.get() == '':
                    showerror('Пароль не выбран', 'Пожалуйста, введите пароль')
                    return None
                key_byte_string += check_key_entry.get().encode('utf-8')    # Если пароль выбран, то добавляем его
            if file_value.get() == 1:
                if check_file_path.get() == '':
                    showerror('Файл не выбран', 'Пожалуйста, выберите файл')
                    return None
                with open(check_file_path.get(), 'rb') as c_file:
                    key_byte_string += c_file.read()                        # Если файл выбран, то добавляем его

            if key_byte_string == b'':  # Если в конце получилась пустая строка, то, скорее всего, файл был пустым
                showerror('Ошибка', 'Нельзя создавать шифрованную ФС без ключа!\nПожалуйста, создайте ключ')
                return None

            self.key = create_key(key_byte_string)              # Создание ключа шифрования
            self.sector_size = int(sector_size_entry.get())     # Запоминаем размер сектора
            if self.sector_size < 512:
                showerror('Слишком малый сектор', 'Пожалуйста, увеличьте размер сектора хотя бы до 512 байт')
                return None
            if self.sector_size > 65536:    # 65536, так как под него отведено всего 2 байта
                showerror('Слишком большой сектор', 'Пожалуйста, уменьшите размер сектора хотя бы до 65536 байт')
                return None

            # Создание заголовков файла
            FirstSector(self.key, self.file_path, self.sector_size).create_new()

            self.tree_sector = TableSector(self.key, self.file_path, 'tree', self.sector_size)
            self.tree_sector.create_new_table()
            self.tree_dict = self.tree_sector.read_table()

            TableSector(self.key, self.file_path, 'file', self.sector_size).create_new_table()
            TableSector(self.key, self.file_path, 'free', self.sector_size).create_new_table()

            # Обновление визуала
            self.tree_visual(0)
            self.folder_visual(0)
            dismiss()

        def open_check_file():
            """Открытие окна выбора контрольного файла"""
            check_file_path.set(filedialog.askopenfilename(title='Выбор контрольного файла'))

        def create_file():
            """Выбор пути для создания файла ФС"""
            self.file_path = filedialog.asksaveasfilename(
                title='Создание файла ФС',
                defaultextension='rlfs',
                initialfile='NewFileSystem.rlfs',
                filetypes=[('rlfs', 'rlfs')])       # rlfs = RockLock FileSystem :)

            path_label['text'] = self.file_path     # Обновление отображаемого пути

        def dismiss():
            """Корректное закрытие окна"""
            window.grab_release()  # Говорим, что окно теперь не приоритетное
            window.destroy()  # И закрываем

    def open_file_system(self):
        window = tk.Toplevel()
        window.title("Открытие файла ФС")
        window.geometry('600x400+660+340')  # Появление в центре экрана (для FHD экранов)
        window.resizable(False, False)
        window.protocol("WM_DELETE_WINDOW", lambda: dismiss())  # перехватываем нажатие на крестик

        # Для красивого отображения
        pad_y = 6
        pad_x = 15

        for i in range(3):
            window.grid_columnconfigure(i, weight=1)
        window.grid_columnconfigure(1, weight=2)
        for i in range(10):
            window.grid_rowconfigure(i, weight=1)

        # Просто заголовок
        ttk.Label(window,
                  text='Открытие зашифрованной файловой системы RockLock',
                  background='grey94', font=font.Font(size=12, underline=True), justify=tk.RIGHT
                  ).grid(row=0, column=0, columnspan=3, pady=20, padx=15)

        # Выбор места
        ttk.Label(window,
                  text='Нажмите на кнопку и выберите файл',
                  background='grey94'
                  ).grid(row=1, column=0, columnspan=3, sticky=tk.W, padx=pad_x, pady=pad_y)

        # Для отображения пути выбранного файла
        path_label = ttk.Label(window,
                               text='',
                               background='white',
                               relief=tk.GROOVE)
        path_label.grid(row=2, column=0, columnspan=2, sticky=tk.EW, padx=pad_x, pady=pad_y, ipadx=2, ipady=2)

        # Сам выбор файла
        ttk.Button(window, text='Обзор...', command=lambda: open_file()).grid(row=2, column=2, sticky=tk.EW, padx=15)

        # Ли-и-и-и-иния
        ttk.Separator(window, orient=tk.HORIZONTAL).grid(row=4, column=0, columnspan=3, sticky=tk.EW, pady=12, padx=10)

        # Выбор метода шифрования (ключ и\или файл)

        ttk.Label(window,
                  text='Введите ключ/ключи',
                  background='grey94'
                  ).grid(row=5, column=0, columnspan=3, sticky=tk.EW, padx=pad_x, pady=pad_y)

        # Галочка для пароля
        self.key_value = tk.IntVar()        # self - Костыль, без него в чек боксе был квадратик
        check_key = ttk.Checkbutton(window, text='Пароль:', variable=self.key_value)
        check_key.grid(row=6, column=0, sticky=tk.E, padx=pad_x, pady=pad_y)

        # Поле для ввода пароля
        check_key_entry = ttk.Entry(window)
        check_key_entry.grid(row=6, column=1, columnspan=2, sticky=tk.EW, padx=pad_x)

        # Галочка для контрольного файла
        self.file_value = tk.IntVar()       # self - Костыль, без него в чек боксе был квадратик
        check_file_path = tk.StringVar()
        check_file = ttk.Checkbutton(window, text='    Файл:', variable=self.file_value)
        check_file.grid(row=7, column=0, sticky=tk.E, padx=pad_x, pady=pad_y)

        check_file_label = ttk.Label(window,
                                     textvariable=check_file_path,
                                     background='white',
                                     relief=tk.GROOVE)
        check_file_label.grid(row=7, column=1, columnspan=2, sticky=tk.EW, padx=pad_x, pady=pad_y, ipadx=2, ipady=2)

        ttk.Button(window, text='Обзор...', command=lambda: open_check_file()
                   ).grid(row=8, column=2, sticky=tk.EW, padx=pad_x)

        # Можно считать, что это невидимый разделитель между основной частью и завершающими кнопками
        tk.Frame(window).grid(row=9, column=0, columnspan=3, pady=12)

        ttk.Button(window, text="Открыть", command=lambda: open_fs()
                   ).grid(row=10, column=0, padx=pad_x, pady=15, sticky=tk.W)
        ttk.Button(window, text="Отмена", command=lambda: dismiss()
                   ).grid(row=10, column=2, padx=pad_x, pady=15, sticky=tk.E)

        window.grab_set()  # Говорим что это приоритетное окно
        # То есть пока его не закрыть к основному окну доступ не получить

        def open_fs():
            """Открытие ФС"""
            # Проверки разные
            if self.file_path == '':
                showerror('Нет файла ФС', 'Пожалуйста, выберите файл файловой системы')
                return None

            key_byte_string = b''
            if self.key_value.get() == 1:
                if check_key_entry.get() == '':
                    showerror('Пароль не выбран', 'Пожалуйста, введите пароль')
                    return None
                key_byte_string += check_key_entry.get().encode('utf-8')  # Если пароль выбран, то добавляем его
            if self.file_value.get() == 1:
                if check_file_path.get() == '':
                    showerror('Файл не выбран', 'Пожалуйста, выберите файл')
                    return None
                with open(check_file_path.get(), 'rb') as c_file:
                    key_byte_string += c_file.read()    # Если файл выбран, то добавляем его

            self.key = create_key(key_byte_string)      # Вычисление ключа шифрования

            sector_0 = FirstSector(self.key, self.file_path)
            head_key, self.sector_size = sector_0.read_sector()   # Чтение проверочного ключа и размера сектора из файла

            if head_key != bytes(gostcrypto.gosthash.new('streebog512', data=bytearray(self.key)).digest()):
                showerror('Неправильный ключ', 'Введен неправильный ключ, попробуйте еще раз')
                return None

            # Узнаем иерархию
            self.tree_sector = TableSector(self.key, self.file_path, 'tree', self.sector_size)
            self.tree_dict = self.tree_sector.read_table()

            # И обновляем визуал
            self.tree_visual(0)
            self.folder_visual(0)
            dismiss()

            # Удаление костылей
            del self.key_value
            del self.file_value

        def open_file():
            """Выбор пути для создания файла ФС"""
            self.file_path = filedialog.askopenfilename(
                title='Открытие файла ФС',
                defaultextension='rlfs',
                initialfile='NewFileSystem.rlfs',
                filetypes=[('rlfs', 'rlfs')])       # rlfs = RockLock FileSystem :)

            path_label['text'] = self.file_path     # Обновление отображаемого пути

        def open_check_file():
            """Открытие окна выбора контрольного файла"""
            check_file_path.set(filedialog.askopenfilename(title='Выбор контрольного файла'))

        def dismiss():
            """Корректное закрытие окна"""
            window.grab_release()  # Говорим, что окно теперь не приоритетное
            window.destroy()  # И закрываем

    def tree_visual(self, selected_node):
        """Визуальное представление дерева иерархии в левой части"""
        selected_node = str(selected_node)                  # Какой элемент выделить в построенном дереве
        for widget in self.tree_frame.winfo_children():     # Отчищаем предыдущее дерево
            widget.destroy()

        # Создаем новое отображение дерева
        self.tree = ttk.Treeview(self.tree_frame)
        self.tree.heading("#0", text='RockLock Explorer', anchor=tk.NW)
        self.tree.pack(expand=1, fill=tk.BOTH)

        # Создаем копию оригинального дерева, чтобы пройтись по всем уровням вложенности
        tree_dict_deep = copy.deepcopy(self.tree_dict)
        max_deep = max([val[5] for val in tree_dict_deep.values()])

        # Строим дерево по уровням вложенности (из-за возможных конфликтов перемещенных элементов)
        for current_deep in range(max_deep + 1):
            for dict_key in list(tree_dict_deep):
                if tree_dict_deep[dict_key][5] == current_deep:
                    self.tree.insert("" if tree_dict_deep[dict_key][0] is None else f'{tree_dict_deep[dict_key][0]}',
                                     tk.END,
                                     dict_key,
                                     text=tree_dict_deep[dict_key][2],
                                     image=self.image_folder_mini if tree_dict_deep[dict_key][
                                                                         3] == 0 else self.image_file_mini,
                                     open=True)
                    del tree_dict_deep[dict_key]    # Удаляем уже использованные ноды, чтобы облегчить дальнейший поиск
        self.tree.selection_set(selected_node)      # Установка выделения на нужно элементе

        def selected_tree(event):
            sel_id = self.tree.selection()[0]   # Определяем какой элемент выделен
            if self.is_looping:                 # Если выделение произошло из-за обратной связи, то ничего не делаем
                self.is_looping = False
            else:                               # Иначе открываем нужную папку (файл из дерева не запустится)
                self.node_open(event, sel_id, False)

        # Если элемент дерева выделился, то запускается функция выше
        self.tree.bind("<<TreeviewSelect>>", selected_tree)

    def folder_visual(self, current_folder_id):
        """Визуальное представление внутренностей папки"""
        for label in self.folders_frame.winfo_children():   # Зачищаем предыдущий вид
            label.destroy()

        for i in range(self.columns):   # Устанавливаем всем столбцам в grid'е равноправие, чтоб ни один не был больше
            self.folders_frame.columnconfigure(i, weight=1)

        child_nodes = self.tree_dict[str(current_folder_id)][1]     # Читаем дочерние узлы нашей папки
        self.update_scrollbar(len(child_nodes))                     # При необходимости рисуем скроллбар

        labels_in_frame = []    # Все элементы, отображаемые в правой части

        def change_background(event, label_id, color):
            """Функция для изменения цвета заднего фона объекта, на который указывает мышь"""
            labels_in_frame[label_id]['background'] = color

        def context_menu_folder_label(event, node_id):
            """Контекстное меню (по нажатию ПКМ), что делать с выделенным файлом/папкой"""
            menu = tk.Menu(tearoff=0)
            menu.add_command(label='Открыть', command=lambda: self.node_open(event, node_id, True))
            menu.add_command(label='Удалить', command=lambda: self.node_remove(event, node_id))
            menu.add_command(label='Переименовать', command=lambda: self.node_rename(event, node_id))
            menu.add_command(label='Переместить', command=lambda: self.node_move(event, node_id))
            menu.add_separator()
            menu.add_command(label='Выгрузить', command=lambda: self.node_unload(event, node_id))
            menu.post(event.x_root, event.y_root)   # Открыть меню по месту нажатия

        for i in range(len(child_nodes)):
            row = i // self.columns     # Определение местоположения в сетке правой части
            col = i % self.columns

            label = ttk.Label(master=self.folders_frame,
                              text=self.tree_dict[str(child_nodes[i])][2],
                              image=self.image_folder_maxi if self.tree_dict[str(child_nodes[i])][3] == 0 else self.image_file_maxi,
                              compound='top',
                              wraplength=self.maxi_ico_size,
                              name=f'label{i}')

            # Собсна, расположение элемента в сетке
            label.grid(row=row, column=col, pady=16)

            # Привязка функций на наведение курсором, выхода курсора с объекта, двойной ЛКМ и одинарный ПКМ
            label.bind('<Enter>', lambda e, label_id=i, color='grey80': change_background(e, label_id, color))
            label.bind('<Leave>', lambda e, label_id=i, color='white': change_background(e, label_id, color))
            label.bind('<Double-ButtonPress-1>',    # Открыть файл/папку по двойному клику ЛКМ
                       lambda e, label_id=str(child_nodes[i]): self.node_open(e, label_id, True))
            label.bind('<Button-3>',                # по нажатию ПКМ открыть контекстное меню
                       lambda e, label_id=str(child_nodes[i]): context_menu_folder_label(e, label_id))

            labels_in_frame.append(label)   # А чтоб элемент не потерялся - заботливо записываем его в список

    def visual_reload(self, node_id):
        """Обновление левой и правой части, плюс запись новой таблицы в файл"""
        self.tree_visual(node_id)
        self.folder_visual(node_id)
        self.tree_sector.update_table(self.tree_dict)

    def node_open(self, event, node_id, can_start_file):
        """Отобразить выбранную папку или запустить файл"""
        node_id = str(node_id)
        if self.tree_dict[node_id][3] == 0:     # Если это папка
            self.folder_visual(node_id)         # Раскрываем папку в правой части
            self.is_looping = True              # Говорим, что из-за этого действия возникнет обратная связь
            self.tree.selection_set(node_id)    # Выделяем нужный элемент в дереве
            self.tree.item(node_id, open=True)  # И открываем его, если он был закрыт
        elif can_start_file:    # Если это файл, то запускаем его (если можем)
            progressbar = ttk.Progressbar(self.status_frame, orient=tk.HORIZONTAL, length=400)
            progressbar.pack(padx=10, pady=10, anchor=tk.E)
            FileSector(self.key, self.file_path, self.sector_size
                       ).exec_file(self.tree_dict[node_id][4], progressbar, self.status_frame)
            progressbar.destroy()

    def node_rename(self, event, node_id):
        """Переименование элемента"""
        node_id = str(node_id)

        # Создание нового окна для переименования (так как я не знаю как сделать так же как в винде)
        window = tk.Toplevel()
        window.title("Переименование")
        window.protocol("WM_DELETE_WINDOW", lambda: dismiss())  # Перехватываем нажатие на крестик

        label = ttk.Label(
            window,
            text=f'Введите новое имя для {"файла" if self.tree_dict[node_id][3] == 1 else "папки"} "{self.tree_dict[node_id][2]}"',
            background='grey94')
        label.pack(anchor=tk.CENTER, expand=1)

        text_entry = ttk.Entry(window)  # Поля для ввода файла
        text_entry.pack(anchor=tk.CENTER, fill=tk.X, expand=1, padx=8, pady=8)

        ok_button = ttk.Button(window, text="Подтвердить", command=lambda: rename())
        ok_button.pack(side=tk.LEFT, anchor=tk.S)
        close_button = ttk.Button(window, text="Отмена", command=lambda: dismiss())
        close_button.pack(side=tk.RIGHT, anchor=tk.S)

        window.grab_set()   # Говорим что это приоритетное окно
        # То есть пока его не закрыть к основному окну доступ не получить

        def rename():
            """Само переименование"""
            self.tree_dict[node_id][2] = text_entry.get()   # Просто меняем имя в дереве
            self.visual_reload(self.tree_dict[node_id][0])  # И говорим, что дерево обновилось, показать обновленный элт
            dismiss()

        def dismiss():
            """Корректное закрытие окна"""
            window.grab_release()   # Говорим, что окно теперь не приоритетное
            window.destroy()        # И закрываем

    def node_remove(self, event, node_id):
        """Удаление элемента"""
        self.iterator = 0   # Итератор для прогрессбара

        def rec_delete(node_id):
            """Рекурсивное удаление папки"""
            for child_id in self.tree_dict[node_id][1]:
                child_id = str(child_id)    # Проходимся по всем дочерним элементам
                rec_delete(child_id)        # И вызываем удаление для них

            if self.tree_dict[node_id][3] == 1:     # Если удаляемый элемент - файл
                FileSector(self.key, self.file_path, self.sector_size).delete_file(self.tree_dict[node_id][4])

            del self.tree_dict[node_id]     # Удаление элемента из дерева

            self.iterator += 1
            progressbar['value'] = float(self.iterator)     # Обновление прогрессбара
            self.status_frame.update()

        result = askyesno(title="Подтверждение", message="Подтвердить удаление?")   # Окно с подтверждением удаления
        if result:                                      # Если пользователь подтвердил
            progressbar = ttk.Progressbar(self.status_frame, orient=tk.HORIZONTAL, length=350, maximum=50.0)
            progressbar.grid(row=0, column=1, padx=10, pady=10, sticky=tk.E)
            self.status_frame.update()                      # То создаем прогрессбар

            par_id = str(self.tree_dict[node_id][0])        # Запоминаем родительский элемент
            self.tree_dict[par_id][1].remove(int(node_id))  # Удаляем из дочерних эл-тов родительского эл-та наш эл-т
            rec_delete(node_id)                             # Рекурсивно удаляем наш элемент

            progressbar['value'] = 100.0                    # Заполняем полностью прогрессбар
            self.status_frame.update()

            self.visual_reload(par_id)                      # И вызываем обновление визуала

            progressbar.destroy()
        del self.iterator

    def node_move(self, event, node_id):
        """Перемещение элемента по дереву"""
        node_id = str(node_id)

        # Создаем новое окно с деревом для выбора папки для перемещения
        window = tk.Toplevel()
        window.title("Перемещение")
        window.protocol("WM_DELETE_WINDOW", lambda: dismiss())  # перехватываем нажатие на крестик

        label = ttk.Label(
            window,
            text=f'Выберите новое местоположение {"файла" if self.tree_dict[node_id][3] == 1 else "папки"} "{self.tree_dict[node_id][2]}"',
            background='grey94')
        label.pack(anchor=tk.CENTER, expand=1, ipady=4)

        moving_tree = ttk.Treeview(window)
        moving_tree.heading("#0", text='RockLock Folders', anchor=tk.NW)
        moving_tree.pack(expand=1, fill=tk.BOTH)

        tree_dict_moving = copy.deepcopy(self.tree_dict)    # Делаем копию нашего дерева

        def rec_delete(node_id):
            """Рекурсивное удаление элементов из копии дерева"""
            for child_id in tree_dict_moving[node_id][1]:
                child_id = str(child_id)
                rec_delete(child_id)
            del tree_dict_moving[node_id]

        par_id = str(tree_dict_moving[node_id][0])          # Узнаем родительский элемент
        rec_delete(node_id)                                 # Удаляем наш элемент из копии дерева
        tree_dict_moving[par_id][1].remove(int(node_id))    # И из родительского элемента
        # Это нужно чтобы не было возможности переместить элемент сам в себя

        # Опять строим дерево по уровням вложенности
        tree_dict_deep = copy.deepcopy(tree_dict_moving)
        max_deep = max([val[5] for val in tree_dict_deep.values()])

        # Строим дерево по уровням вложенности (из-за возможных конфликтов перемещенных элементов)
        for current_deep in range(max_deep + 1):
            for dict_key in list(tree_dict_deep):
                # Строим только папки
                if tree_dict_deep[dict_key][5] == current_deep and tree_dict_deep[dict_key][3] == 0:
                    moving_tree.insert("" if tree_dict_deep[dict_key][0] is None else f'{tree_dict_deep[dict_key][0]}',
                                       tk.END,
                                       dict_key,
                                       text=tree_dict_deep[dict_key][2],
                                       image=self.image_folder_mini,
                                       open=True)
                    del tree_dict_deep[dict_key]    # Удаляем уже использованные ноды, чтобы облегчить дальнейший поиск

        ok_button = ttk.Button(window, text="Подтвердить", command=lambda: move())
        ok_button.pack(side=tk.LEFT, anchor=tk.S)
        close_button = ttk.Button(window, text="Отмена", command=lambda: dismiss())
        close_button.pack(side=tk.RIGHT, anchor=tk.S)

        window.grab_set()   # Ставим новому окну приоритет

        def move():
            """Само перемещение элемента"""
            target_node_id = str(moving_tree.selection()[0])    # Определяем выделенный в новом дереве элемент
            parent_id = str(self.tree_dict[node_id][0])         # Определяем родительский элемент нашего элемента

            self.tree_dict[parent_id][1].remove(int(node_id))   # Удаляем наш элемент из дочерних родительского
            self.tree_dict[node_id][0] = int(target_node_id)    # Перезаписываем родительский элемент на выбранный
            self.tree_dict[target_node_id][1].append(int(node_id))  # Прибавляем элемент к дочерним выбранного
            self.tree_dict[node_id][5] = self.tree_dict[target_node_id][5] + 1  # Прописываем новый уровень вложенности

            self.visual_reload(target_node_id)  # И обновляем визуал, как же без этого
            dismiss()   # Закрываем окно перемещения

        def dismiss():
            """Корректное закрытие окна"""
            window.grab_release()  # Говорим, что окно теперь не приоритетное
            window.destroy()  # И закрываем

    def node_create(self, event, parent_id):
        """Создание новой папки"""
        new_id = str(int(list(self.tree_dict.keys())[-1]) + 1)  # В качестве нового id - последний +1

        name = 'New Folder'                     # Назначаем имя новой папки
        child_names = [self.tree_dict[str(i)][2] for i in self.tree_dict[parent_id][1]]
        iterator = 1
        while name in child_names:
            name = f'New Folder ({iterator})'   # Если такое имя уже занято, то приписываем (1) или (2) и тд
            iterator += 1

        folder = [int(parent_id), [], name, 0, 0, self.tree_dict[str(parent_id)][5] + 1]    # Шаблон пустой папки
        self.tree_dict[new_id] = folder                     # Записываем его в дерево
        self.tree_dict[parent_id][1].append(int(new_id))    # И добавляем в дочерние родительского элемента

        self.visual_reload(parent_id)   # Перезагружаем графику и сохраняем дерево

    def node_file_load(self, event, parent_id):
        """Загрузка одного файла в ФС"""
        new_id = str(int(list(self.tree_dict.keys())[-1]) + 1)  # В качестве нового id - последний +1

        load_file_path = filedialog.askopenfilename(title='Выбор файла для загрузки')
        if load_file_path != '':
            progressbar = ttk.Progressbar(self.status_frame, orient=tk.HORIZONTAL, length=400)
            progressbar.grid(row=0, column=1, padx=10, pady=10, sticky=tk.E)

            # Загружаем файл в таблицу файлов
            file_id, file_name = FileSector(self.key, self.file_path, self.sector_size
                                            ).write_file(load_file_path, progressbar, self.status_frame)

            # И добавляем в таблицу дерева
            self.tree_dict[new_id] = [int(parent_id), [], file_name, 1, file_id, self.tree_dict[str(parent_id)][5] + 1]
            self.tree_dict[str(parent_id)][1].append(int(new_id))

            self.visual_reload(parent_id)   # Обновляем визуал и сохраняем дерево
            progressbar.destroy()

    def node_folder_load(self, event, parent_id):
        """Загрузка целой папки в ФС"""
        directory_path = filedialog.askdirectory(title='Выбор папки для загрузки')      # Окно выбора
        if directory_path != '':            # Если что-то выбрал
            directory_path = directory_path.replace('/', '\\')
            dir_root = directory_path[:directory_path.rfind('\\')]

            # Создаем целых два прогрессбара, один для отдельных файлов, другой для всей папки
            progressbar = ttk.Progressbar(self.status_frame, orient=tk.HORIZONTAL, length=350)
            progressbar.grid(row=0, column=1, padx=10, pady=10, sticky=tk.E)

            progressbar_total = ttk.Progressbar(self.status_frame, orient=tk.HORIZONTAL, length=350)
            progressbar_total.grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)

            new_id = str(int(list(self.tree_dict.keys())[-1]) + 1)  # В качестве нового id - последний +1
            all_files = list(os.walk(directory_path))               # Узнаем все подфайлы в этой папке

            num_files = 0
            for _, _, files in all_files:       # Считаем их для корректного отображения общего прогресбара
                num_files += 1
                for _ in files:
                    num_files += 1

            progressbar_total['maximum'] = float(num_files)
            self.status_frame.update()

            file_sector = FileSector(self.key, self.file_path, self.sector_size)     # Открываем секторы файлов

            iterator = -1   # Для общего прогрессбара
            parent_dict = {dir_root: str(parent_id), directory_path: new_id}        # К какой ветке приписать файл/папку
            for address, dirs, files in all_files:                  # Проходимся по всем подпапкам
                iterator += 1
                progressbar_total['value'] = float(iterator)        # Обновляем общий прогрессбар
                self.status_frame.update()

                address_root = address[:address.rfind('\\')]
                par_id = parent_dict[address_root]                  # Узнаем родителя

                address_name = address[address.rfind('\\') + 1:]
                self.tree_dict[new_id] = [int(par_id), [], address_name, 0, 0, self.tree_dict[par_id][5] + 1]
                self.tree_dict[par_id][1].append(int(new_id))       # И вписываем текущую папку в дерево

                par_id = new_id
                for child_folder in dirs:                           # Смотрим на подпапки
                    new_id = str(int(new_id) + 1)                   # И создаем для них родительские id
                    parent_dict[address + '\\' + child_folder] = new_id

                for child_file in files:                            # Смотрим на все файлы в папке
                    iterator += 1
                    progressbar_total['value'] = float(iterator)
                    self.status_frame.update()

                    # Загружаем в сектора файлов
                    file_id, _ = file_sector.write_file(address + '\\' + child_file, progressbar, self.status_frame)

                    # И кладем в дерево
                    new_id = str(int(new_id) + 1)
                    self.tree_dict[new_id] = [int(par_id), [], child_file, 1, file_id, self.tree_dict[par_id][5] + 1]
                    self.tree_dict[par_id][1].append(int(new_id))

                new_id = str(int(new_id) + 1)   # Переходим к следующий папке

            progressbar_total['value'] = float(num_files)
            self.status_frame.update()

            self.visual_reload(parent_id)

            progressbar.destroy()
            progressbar_total.destroy()

    def node_unload(self, event, node_id):
        """Выгрузка файла или папки из ФС в ФС ОС"""
        def rec_nod_bypass(path, child_id):
            if self.tree_dict[child_id][3] == 0:            # Если элемент - папка
                node_name = self.tree_dict[child_id][2]     # Имя папки (по-хорошему добавить проверку, но лень)
                os.mkdir(path + '\\' + node_name)           # Создаем нужную папку

                for child_node in self.tree_dict[child_id][1]:  # Если есть дочерние элементы, то обходим и их
                    child_node = str(child_node)
                    rec_nod_bypass(path + '\\' + node_name, child_node)
            else:                                           # Если элемент - файл
                file_name, file_bytes = FileSector(         # То читаем файл
                    self.key, self.file_path, self.sector_size
                ).read_file(self.tree_dict[child_id][4], progressbar, self.status_frame)

                with open(path + '\\' + file_name, 'wb') as f:      # И создаем его в папке
                    f.write(file_bytes)
            progressbar_total['value'] = progressbar['value'] + 1.0
            self.status_frame.update()

        node_id = str(node_id)
        directory_path = filedialog.askdirectory(title='Выбор места выгрузки')      # Окно выбора
        if directory_path != '':
            # Создаем целых два прогрессбара, один для отдельных файлов, другой для всей папки
            progressbar = ttk.Progressbar(self.status_frame, orient=tk.HORIZONTAL, length=350)
            progressbar.grid(row=0, column=1, padx=10, pady=10, sticky=tk.E)

            progressbar_total = ttk.Progressbar(self.status_frame, orient=tk.HORIZONTAL, length=350, maximum=100.0)
            progressbar_total.grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)

            directory_path = directory_path.replace('/', '\\')

            rec_nod_bypass(directory_path, node_id)     # Начинаем рекурсивную выгрузку папок и подпапок
            progressbar_total['value'] = 100.0
            self.status_frame.update()

            progressbar.destroy()
            progressbar_total.destroy()


def main():
    pass


if __name__ == '__main__':
    main()
