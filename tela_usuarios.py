import sys
import os
import json
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTabWidget,
    QTreeView, QAbstractItemView, QHeaderView,
    QInputDialog, QMessageBox, QLineEdit
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt, QModelIndex
from ..backend.storage_db import (
    load_usuarios,
    load_solicitacoes,
    insert_usuario,
    delete_solicitacao
)

class TelaUsuarios(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("telaUsuarios")  
        self.setWindowTitle("Gerenciamento de Usuários")
        self.resize(700, 500)

        # caminhos dos JSONs na raiz do projeto (caso ainda precise deles)
        root = os.getcwd()
        self.users_path = os.path.join(root, "usuarios.json")
        self.req_path   = os.path.join(root, "solicitacoes.json")

        self._load_data()
        self._build_ui()

    def _load_data(self):
        """Carrega usuários e solicitações direto do banco."""
        # --- Usuários ---
        self.usuarios = load_usuarios()

        # --- Solicitações ---
        raw_req = load_solicitacoes()
        self.solicitantes = {
            req['usuario']: {'nome': req['nome'], 'senha': req['senha_hash']}
            for req in raw_req
        }

    def _build_ui(self):
        lay = QVBoxLayout(self)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs)

        # aba Usuários
        tab1 = QWidget(); l1 = QVBoxLayout(tab1)
        self.tree_users = QTreeView()
        self.model_users = QStandardItemModel()
        self.model_users.setHorizontalHeaderLabels(["Nome", "Cargo", "Senha"])
        self.tree_users.setModel(self.model_users)
        # desabilita edição direta
        self.tree_users.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        # faz colunas preencher todo o espaço
        self.tree_users.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # sinal de duplo-clique
        self.tree_users.doubleClicked.connect(self._on_user_double_clicked)
        l1.addWidget(self.tree_users)
        self.tabs.addTab(tab1, "Usuários")

        # aba Solicitações
        tab2 = QWidget(); l2 = QVBoxLayout(tab2)
        self.tree_reqs = QTreeView()
        self.model_reqs = QStandardItemModel()
        self.model_reqs.setHorizontalHeaderLabels(["Nome", "Login"])
        self.tree_reqs.setModel(self.model_reqs)
        self.tree_reqs.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree_reqs.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tree_reqs.doubleClicked.connect(self._on_request_double_clicked)
        l2.addWidget(self.tree_reqs)
        self.tabs.addTab(tab2, "Solicitações")

        # popula ambas as views
        self._populate_users()
        self._populate_requests()

    def _populate_users(self):
        """
        Preenche a árvore de usuários com todos os registros em self.usuarios.
        """
        # Apaga todas as linhas anteriores
        self.model_users.removeRows(0, self.model_users.rowCount())

        for key, info in self.usuarios.items():
            nome_item  = QStandardItem(info.get("nome", ""))
            cargo_item = QStandardItem(info.get("cargo", ""))
            senha_item = QStandardItem(info.get("senha", ""))

            # armazena a key no UserRole para recuperar depois
            nome_item.setData(key, Qt.ItemDataRole.UserRole)

            # adiciona a linha inteira ao modelo
            self.model_users.appendRow([nome_item, cargo_item, senha_item])

    def _populate_requests(self):
        """
        Preenche a árvore de solicitações com todos os registros em self.solicitantes.
        """
        self.model_reqs.removeRows(0, self.model_reqs.rowCount())

        for login, info in self.solicitantes.items():
            nome_item  = QStandardItem(info.get("nome", ""))
            login_item = QStandardItem(login)
            # armazena o login no UserRole
            nome_item.setData(login, Qt.ItemDataRole.UserRole)
            self.model_reqs.appendRow([nome_item, login_item])

        # Atualiza o título da aba com bolinha se houver solicitações
        count = self.model_reqs.rowCount()
        label = "Solicitações" + (" ●" if count else "")
        self.tabs.setTabText(1, label)

    def _on_user_double_clicked(self, index: QModelIndex):
        """****
        Duplo clique em um usuário: permite alterar cargo (col=1) ou senha (col=2).
        """
        row = index.row()
        col = index.column()
        # Recupera a key (login) que guardamos em UserRole
        key = self.model_users.item(row, 0).data(Qt.ItemDataRole.UserRole)
        info = self.usuarios.get(key, {})
        nome = info.get("nome", key)
        if col == 1:  # alterar cargo
            old = info.get("cargo", "")
            cargos = ["Administrativo", "Gerente", "Técnico"]
            idx = cargos.index(old) if old in cargos else 0
            novo, ok = QInputDialog.getItem(
                self, "Alterar Cargo",
                f"Cargo para {nome}:", cargos, idx, False
            )
            if ok and novo != old:
                info["cargo"] = novo
                self.model_users.item(row, 1).setText(novo)
                self._save_json(self.users_path, self.usuarios)

        elif col == 2:  # alterar senha
            old = info.get("senha", "")
            novo, ok = QInputDialog.getText(
                self, "Alterar Senha",
                f"Senha para {nome}:",
                QLineEdit.EchoMode.Password, old
            )
            if ok and novo and novo != old:
                info["senha"] = novo
                self.model_users.item(row, 2).setText(novo)
                self._save_json(self.users_path, self.usuarios)

    def _on_request_double_clicked(self, index: QModelIndex):
        """
        Duplo clique em uma solicitação: oferece aceitar ou recusar.
        """
        row = index.row()
        login = self.model_reqs.item(row, 0).data(Qt.ItemDataRole.UserRole)
        info  = self.solicitantes.get(login, {})
        nome  = info.get("nome", login)
        senha = info.get("senha", "")

        msg = QMessageBox(self.window())
        msg.setWindowTitle("Solicitação de Acesso")
        msg.setText(
            f"Solicitação de acesso de\n\n"
            f"Nome: {nome}\nLogin: {login}\n\nDeseja aceitar ou recusar?"
        )
        aceitar_btn = msg.addButton("Aceitar",  QMessageBox.ButtonRole.AcceptRole)
        recusar_btn = msg.addButton("Recusar", QMessageBox.ButtonRole.RejectRole)
        msg.exec()

        if msg.clickedButton() == aceitar_btn:
            cargos = ["CEO", "Administrativo", "Gerente", "Técnico"]
            novo_cargo, ok = QInputDialog.getItem(
                self, "Cargo", f"Atribuir cargo a {nome}:", cargos, 0, False
            )
            if not ok:
                return

            insert_usuario(login, senha, nome, novo_cargo)
            delete_solicitacao(login)

        elif msg.clickedButton() == recusar_btn:
            delete_solicitacao(login)
        else:
            return

        # Recarrega do banco e atualiza as views
        self.usuarios     = load_usuarios()
        raw_req          = load_solicitacoes()
        self.solicitantes = {r['usuario']: r for r in raw_req}
        self._populate_users()
        self._populate_requests()

        acao = "aceito" if msg.clickedButton() == aceitar_btn else "recusado"
        QMessageBox.information(self.window(), "Sucesso", f"{nome} {acao} com sucesso!")

    def _save_json(self, path, data):
        """
        Salva um dicionário em JSON (caso você queira persistir alterações locais).
        """
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            QMessageBox.critical(self, "Erro ao salvar JSON", str(e))

    def cleanup(self):
        """
        Opcional: desconecta sinais para evitar que erros aconteçam
        depois que o widget for destruído.
        """
        try:
            self.tree_reqs.doubleClicked.disconnect(self._on_request_double_clicked)
        except (TypeError, RuntimeError):
            pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    tela = TelaUsuarios()
    tela.show()
    sys.exit(app.exec())
