import json
import os
import zlib
import gostcrypto
import tkinter as tk
from tkinter import ttk     # Современно выглядящие виджеты
from tkinter.messagebox import askyesno
from PIL import Image, ImageTk
import copy


class VisualElements:
    def __init__(self, tree_dict):
        self.columns = 4     # По-хорошему регулировать в зависимости от размера окна, но пока так
        self.tree_dict = tree_dict

        # Рандомные переменные
        self.labels = []
        self.is_looping = False

        # Собсна интерфейс
        self.root = tk.Tk()
        self.root.title("RockLock")
        self.root.geometry("800x600")
        self.root.resizable(False, False)
        self.root.option_add("*tearOff", tk.FALSE)

        # Картинки!
        mini_ico_size = 14
        self.maxi_ico_size = 80
        self.image_folder_mini = ImageTk.PhotoImage(Image.open('folder_ico.png').resize((mini_ico_size, mini_ico_size)))
        self.image_folder_maxi = ImageTk.PhotoImage(Image.open('folder_ico.png').resize((self.maxi_ico_size, self.maxi_ico_size)))
        self.image_file_mini = ImageTk.PhotoImage(Image.open('file_ico.png').resize((mini_ico_size, mini_ico_size)))
        self.image_file_maxi = ImageTk.PhotoImage(Image.open('file_ico.png').resize((self.maxi_ico_size, self.maxi_ico_size)))

        # Главное меню
        main_menu = tk.Menu()

        file_menu = tk.Menu()
        file_menu.add_command(label="New")
        file_menu.add_command(label="Save")
        file_menu.add_command(label="Open")
        file_menu.add_separator()
        file_menu.add_command(label="Exit")

        main_menu.add_cascade(label="File", menu=file_menu)
        main_menu.add_cascade(label="Edit")
        main_menu.add_cascade(label="View")
        self.root.config(menu=main_menu)

        # Немного стиля
        label_style = ttk.Style()
        label_style.configure("TFrame", background='white')  # фоновый цвет
        label_style.configure("TLabel", background='white')  # фоновый цвет

        # Фрейм для иерархического дерева
        self.tree_frame = ttk.Frame(master=self.root, borderwidth=0, relief=tk.GROOVE)
        self.tree_frame.pack(side=tk.LEFT, anchor=tk.N, fill=tk.Y, pady=3, padx=2)

        self.tree = ttk.Treeview(master=self.tree_frame)
        self.tree.heading("#0", text='RockLock Explorer', anchor=tk.NW)
        self.tree.pack(expand=1, fill=tk.BOTH)

        # Фрейм для отображения папок и файлов и настройка его скроллбара
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

        # Заполнение
        self.tree_visual(0)      # Дерево слева
        self.folder_visual(0)   # Вывод папок справа

        def context_menu_folder_frame(event):
            parent_id = self.tree.selection()[0]
            menu = tk.Menu(tearoff=0)
            menu.add_command(label='Создать папку', command=lambda: self.node_create(event, parent_id))
            menu.add_separator()
            menu.add_command(label='Загрузить файл')
            menu.add_command(label='Загрузить папку')
            menu.post(event.x_root, event.y_root)

        self.canvas.bind('<Button-3>', context_menu_folder_frame)
        self.folders_frame.bind('<Button-3>', context_menu_folder_frame)

        self.root.mainloop()

    def _on_mouse_wheel(self, event):
        # Прокрутка вверх/вниз в зависимости от направления колеса
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def update_scrollbar(self, num_elements):
        # Проверяем количество строк и активируем или отключаем скроллбар
        if num_elements > 16:
            self.scrollbar.grid(row=0, column=1, sticky=tk.NS)
            self.canvas.configure(yscrollcommand=self.scrollbar.set)
        else:
            self.scrollbar.grid_forget()
            self.canvas.configure(yscrollcommand="")

    def tree_visual(self, selected_node):
        selected_node = str(selected_node)
        for widget in self.tree_frame.winfo_children():
            widget.destroy()
        self.tree = ttk.Treeview(master=self.tree_frame)
        self.tree.heading("#0", text='RockLock Explorer', anchor=tk.NW)
        self.tree.pack(expand=1, fill=tk.BOTH)

        tree_dict_deep = copy.deepcopy(self.tree_dict)
        deeps = [val[5] for val in tree_dict_deep.values()]
        max_deep = max(deeps)

        for current_deep in range(max_deep+1):
            for key in list(tree_dict_deep):
                if tree_dict_deep[key][5] == current_deep:
                    self.tree.insert("" if self.tree_dict[key][0] is None else f'{self.tree_dict[key][0]}',
                                     tk.END,
                                     key,
                                     text=self.tree_dict[key][2],
                                     image=self.image_folder_mini if self.tree_dict[key][
                                                                         3] == 0 else self.image_file_mini,
                                     open=True)
                    del tree_dict_deep[key]

        self.tree.selection_set(selected_node)

        def selected_tree(event):
            sel_id = self.tree.selection()[0]
            if self.is_looping:
                self.is_looping = False
            else:
                self.node_open(event, sel_id, False)

        # def rbm_selected_tree(event):
        #     sel_id = self.tree.selection()[0]
        #     self.context_menu_folder_label(event, sel_id)

        self.tree.bind("<<TreeviewSelect>>", selected_tree)
        # tree.bind('<Button-3>', rbm_selected_tree)

    def folder_visual(self, current_folder_id):
        for label in self.folders_frame.winfo_children():   # Зачищаем предыдущий вид
            label.destroy()

        for i in range(self.columns):
            self.folders_frame.columnconfigure(i, weight=1)

        child_nodes = self.tree_dict[str(current_folder_id)][1]
        self.update_scrollbar(len(child_nodes))

        def change_background(event, label_id, color):
            self.labels[label_id]['background'] = color

        def context_menu_folder_label(event, node_id):
            menu = tk.Menu(tearoff=0)
            menu.add_command(label='Открыть', command=lambda: self.node_open(event, node_id, True))
            menu.add_command(label='Удалить', command=lambda: self.node_remove(event, node_id))
            menu.add_command(label='Переименовать', command=lambda: self.node_rename(event, node_id))
            menu.add_command(label='Переместить', command=lambda: self.node_move(event, node_id))
            menu.post(event.x_root, event.y_root)

        self.labels = []
        for i in range(len(child_nodes)):
            row = i // self.columns
            col = i % self.columns

            label = ttk.Label(master=self.folders_frame,
                              text=self.tree_dict[str(child_nodes[i])][2],
                              image=self.image_folder_maxi if self.tree_dict[str(child_nodes[i])][3] == 0 else self.image_file_maxi,
                              compound='top',
                              wraplength=self.maxi_ico_size,
                              name=f'label{i}')

            label.grid(row=row, column=col, pady=16)

            label.bind('<Enter>', lambda e, label_id=i, color='grey80': change_background(e, label_id, color))
            label.bind('<Leave>', lambda e, label_id=i, color='white': change_background(e, label_id, color))
            label.bind('<Double-ButtonPress-1>', lambda e, label_id=str(child_nodes[i]): self.node_open(e, label_id, True))
            label.bind('<Button-3>', lambda e, label_id=str(child_nodes[i]): context_menu_folder_label(e, label_id))

            self.labels.append(label)


    # Обновление отображаемых элементов
    def visual_reload(self, node_id):
        self.tree_visual(node_id)
        self.folder_visual(node_id)
        # tree_changed()      # Функция для сохранения измененного дерева

    # Отобразить содержимое выбранной папки, раскрыть дочерние элементы в дереве
    def node_open(self, event, node_id, can_start_file):
        node_id = str(node_id)
        if self.tree_dict[node_id][3] == 0:     # Если это папка
            self.folder_visual(node_id)
            self.is_looping = True
            self.tree.selection_set(node_id)
            self.tree.item(node_id, open=True)
        elif can_start_file:
            print(f'Запуск файла {node_id} - {self.tree_dict[node_id][4]}')

    def node_rename(self, event, node_id):
        node_id = str(node_id)

        window = tk.Toplevel()
        window.title("Переименование")
        window.protocol("WM_DELETE_WINDOW", lambda: dismiss())  # перехватываем нажатие на крестик

        label = ttk.Label(
            window,
            text=f'Введите новое имя для {"файла" if self.tree_dict[node_id][3] == 1 else "папки"} "{self.tree_dict[node_id][2]}"',
            background='grey94')
        label.pack(anchor=tk.CENTER, expand=1)

        text_entry = ttk.Entry(window)
        text_entry.pack(anchor=tk.CENTER, fill=tk.X, expand=1, padx=8, pady=8)

        ok_button = ttk.Button(window, text="Подтвердить", command=lambda: rename())
        ok_button.pack(side=tk.LEFT, anchor=tk.S)
        close_button = ttk.Button(window, text="Отмена", command=lambda: dismiss())
        close_button.pack(side=tk.RIGHT, anchor=tk.S)

        window.grab_set()

        def rename():
            self.tree_dict[node_id][2] = text_entry.get()   # Само переименование в дереве
            self.visual_reload(self.tree_dict[node_id][0])
            dismiss()

        def dismiss():
            window.grab_release()
            window.destroy()

    def node_remove(self, event, node_id):
        def rec_delete(node_id):
            for child_id in self.tree_dict[node_id][1]:
                child_id = str(child_id)
                rec_delete(child_id)
            del self.tree_dict[node_id]
        result = askyesno(title="Подтверждение", message="Подтвердить удаление?")

        if result:
            par_id = str(self.tree_dict[node_id][0])
            self.tree_dict[par_id][1].remove(int(node_id))
            rec_delete(node_id)
            self.visual_reload(par_id)

    def node_move(self, event, node_id):
        node_id = str(node_id)
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

        tree_dict_moving = copy.deepcopy(self.tree_dict)

        def rec_delete(node_id):
            for child_id in tree_dict_moving[node_id][1]:
                child_id = str(child_id)
                rec_delete(child_id)
            del tree_dict_moving[node_id]

        par_id = str(tree_dict_moving[node_id][0])
        rec_delete(node_id)
        tree_dict_moving[par_id][1].remove(int(node_id))

        for key in list(tree_dict_moving):
            if tree_dict_moving[key][3] == 0:
                moving_tree.insert("" if tree_dict_moving[key][0] is None else f'{tree_dict_moving[key][0]}',
                            tk.END,
                            key,
                            text=tree_dict_moving[key][2],
                            image=self.image_folder_mini,
                            open=True if tree_dict_moving[key][0] is None else False)

        ok_button = ttk.Button(window, text="Подтвердить", command=lambda: move())
        ok_button.pack(side=tk.LEFT, anchor=tk.S)
        close_button = ttk.Button(window, text="Отмена", command=lambda: dismiss())
        close_button.pack(side=tk.RIGHT, anchor=tk.S)

        window.grab_set()

        def move():
            target_node_id = str(moving_tree.selection()[0])
            parent_id = str(self.tree_dict[node_id][0])

            self.tree_dict[parent_id][1].remove(int(node_id))
            self.tree_dict[node_id][0] = int(target_node_id)
            self.tree_dict[target_node_id][1].append(int(node_id))
            self.tree_dict[node_id][5] = self.tree_dict[target_node_id][5] + 1

            self.visual_reload(target_node_id)
            dismiss()

        def dismiss():
            window.grab_release()
            window.destroy()

    def node_create(self, event, parent_id):
        new_id = str(int(list(self.tree_dict.keys())[-1]) + 1)
        name = 'New Folder'
        child_names = [self.tree_dict[str(i)][2] for i in self.tree_dict[parent_id][1]]

        iterator = 1
        while name in child_names:
            name = f'New Folder ({iterator})'
            iterator += 1

        folder = [int(parent_id), [], name, 0, 0, self.tree_dict[str(parent_id)][5] + 1]
        self.tree_dict[new_id] = folder
        self.tree_dict[parent_id][1].append(int(new_id))

        self.visual_reload(parent_id)

    def node__file_load(self, event, parent_id):
        pass

    def node_folder_load(self, event, parent_id):
        pass


def main():
    # print(pow(2, 31))

    # id - par_id - child_id_list - name - is_file - file_id - deep
    # key -  0    -      1        -  2   -    3    -    4    -  5
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

    json_tree = json.dumps(tree, separators=(',', ':')).encode('utf-8')
    print(json_tree)
    # print(len(json_tree))
    # print(len(zlib.compress(json_tree, 1)))

    tree_dict = json.loads(json_tree)

    print(tree_dict.keys())







if __name__ == '__main__':
    main()