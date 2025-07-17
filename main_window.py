# main/frontend/main_window.py

import os
import sys
import logging
import time
from typing import Dict, Optional, List, Tuple, Any
from pathlib import Path
from datetime import datetime, timedelta
import threading
from functools import lru_cache
import hashlib
from dataclasses import dataclass
from threading import Lock

from PyQt6.QtWidgets import (
    QMainWindow, QHeaderView, QVBoxLayout, QTableWidget, QPushButton, 
    QLabel, QSizePolicy, QTableView, QProgressDialog, QApplication,
    QHBoxLayout, QWidget, QStackedWidget, QMenu, QSystemTrayIcon
)
from PyQt6.QtCore import Qt, QSize, QEvent, QPoint, QPropertyAnimation, QTimer, QByteArray
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtGui import QIcon, QPixmap, QImage

# Imports locais
from .tela_usuarios import TelaUsuarios
from .cadastrar_os_page import CadastrarOSPage
from .tela_conficuraçoes import ConfiguracoesUsuarioDialog
from .tela_grafico import TelaGraficos
from ..backend.storage_db import load_solicitacoes
from .abrir_os_page import AbrirOSPage
from .status_os_page import StatusOSPage
from ..backend.db_connection import health_check, conectar_banco

from .resumo import Resumo

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class CacheConfig:
    """Configurações do cache de imagens"""
    MAX_SIZE: int = 100  # Número máximo de imagens
    CLEANUP_THRESHOLD: float = 0.8  # 80% do tamanho máximo
    MAX_AGE: int = 3600  # 1 hora em segundos
    COMPRESSION_QUALITY: int = 85  # Qualidade da compressão (0-100)
    MIN_COMPRESSION_SIZE: int = 1024 * 1024  # 1MB
    MAX_DIMENSION: int = 2048  # Dimensão máxima em pixels
    CLEANUP_INTERVAL: int = 300  # 5 minutos em segundos

class ImageCache:
    """Sistema de cache de imagens otimizado"""
    
    def __init__(self):
        self._cache: Dict[str, Tuple[QPixmap, float, int]] = {}  # path -> (pixmap, timestamp, size)
        self._access_count: Dict[str, int] = {}  # path -> contagem de acessos
        self._lock = Lock()
        self._last_cleanup = time.time()
        
        # Configuração de logging
        self._logger = logging.getLogger(__name__)
        
        # Timer para limpeza periódica
        self._cleanup_timer = QTimer()
        self._cleanup_timer.timeout.connect(self._periodic_cleanup)
        self._cleanup_timer.start(CacheConfig.CLEANUP_INTERVAL * 1000)
    
    def _get_file_hash(self, path: str) -> str:
        """Gera hash único para arquivo"""
        try:
            with open(path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            self._logger.error(f"Erro ao gerar hash do arquivo {path}: {e}")
            return str(time.time())  # Fallback
    
    def _should_compress(self, size: int, width: int, height: int) -> bool:
        """Verifica se imagem deve ser comprimida"""
        return (
            size > CacheConfig.MIN_COMPRESSION_SIZE or
            width > CacheConfig.MAX_DIMENSION or
            height > CacheConfig.MAX_DIMENSION
        )
    
    def _compress_pixmap(self, pixmap: QPixmap) -> QPixmap:
        """Comprime imagem mantendo proporção"""
        if pixmap.isNull():
            return pixmap
            
        # Converte para QImage para compressão
        image = pixmap.toImage()
        width = image.width()
        height = image.height()
        
        # Redimensiona se necessário
        if width > CacheConfig.MAX_DIMENSION or height > CacheConfig.MAX_DIMENSION:
            if width > height:
                new_width = CacheConfig.MAX_DIMENSION
                new_height = int(height * (CacheConfig.MAX_DIMENSION / width))
            else:
                new_height = CacheConfig.MAX_DIMENSION
                new_width = int(width * (CacheConfig.MAX_DIMENSION / height))
                
            image = image.scaled(
                new_width,
                new_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        
        # Comprime
        buffer = QByteArray()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "JPEG", CacheConfig.COMPRESSION_QUALITY)
        
        # Converte de volta para QPixmap
        compressed = QPixmap()
        compressed.loadFromData(buffer)
        
        return compressed
    
    def _cleanup(self) -> None:
        """Remove itens menos acessados e mais antigos"""
        with self._lock:
            if len(self._cache) < CacheConfig.MAX_SIZE * CacheConfig.CLEANUP_THRESHOLD:
                return
                
            # Ordena por acesso e idade
            items = sorted(
                self._cache.items(),
                key=lambda x: (
                    self._access_count.get(x[0], 0),
                    x[1][1]  # timestamp
                )
            )
            
            # Remove 20% dos itens menos acessados
            to_remove = int(len(items) * 0.2)
            for path, _ in items[:to_remove]:
                self._cache.pop(path, None)
                self._access_count.pop(path, None)
                
            self._logger.info(f"Cache limpo: {to_remove} itens removidos")
    
    def _periodic_cleanup(self) -> None:
        """Limpeza periódica do cache"""
        now = time.time()
        if now - self._last_cleanup < CacheConfig.CLEANUP_INTERVAL:
            return
            
        self._last_cleanup = now
        self._cleanup()
    
    def get_pixmap(self, path: str) -> Optional[QPixmap]:
        """Obtém imagem do cache ou carrega se não existir"""
        if not os.path.exists(path):
            self._logger.error(f"Arquivo não encontrado: {path}")
            return None
            
        with self._lock:
            # Verifica cache
            if path in self._cache:
                pixmap, timestamp, _ = self._cache[path]
                
                # Verifica idade
                if time.time() - timestamp > CacheConfig.MAX_AGE:
                    self._cache.pop(path)
                    self._access_count.pop(path, None)
                else:
                    self._access_count[path] = self._access_count.get(path, 0) + 1
                    return pixmap
            
            try:
                # Carrega imagem
                pixmap = QPixmap(path)
                if pixmap.isNull():
                    self._logger.error(f"Falha ao carregar imagem: {path}")
                    return None
                
                # Verifica se deve comprimir
                file_size = os.path.getsize(path)
                if self._should_compress(file_size, pixmap.width(), pixmap.height()):
                    pixmap = self._compress_pixmap(pixmap)
                
                # Adiciona ao cache
                self._cache[path] = (pixmap, time.time(), file_size)
                self._access_count[path] = 1
                
                # Verifica limite
                if len(self._cache) >= CacheConfig.MAX_SIZE:
                    self._cleanup()
                
                return pixmap
                
            except Exception as e:
                self._logger.error(f"Erro ao processar imagem {path}: {e}")
                return None
    
    def clear(self) -> None:
        """Limpa cache"""
        with self._lock:
            self._cache.clear()
            self._access_count.clear()
            self._logger.info("Cache limpo")
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache"""
        with self._lock:
            return {
                "total_items": len(self._cache),
                "max_size": CacheConfig.MAX_SIZE,
                "total_size": sum(size for _, _, size in self._cache.values()),
                "most_accessed": sorted(
                    self._access_count.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5]
            }
    
    def set_max_size(self, size: int) -> None:
        """Ajusta tamanho máximo do cache"""
        with self._lock:
            CacheConfig.MAX_SIZE = max(1, size)
            if len(self._cache) > size:
                self._cleanup()
    
    def set_compression_quality(self, quality: int) -> None:
        """Ajusta qualidade da compressão"""
        with self._lock:
            CacheConfig.COMPRESSION_QUALITY = max(0, min(100, quality))

class MainWindow(QMainWindow):
    """Janela principal da aplicação"""
    
    # Constantes
    SIDEBAR_WIDTH = 150
    ANIMATION_DURATION = 300
    BUTTON_SIZE = (30, 30)
    ICON_SIZE = (22, 22)
    SIDEBAR_ICON_SIZE = (30, 30)
    
    # Cargos válidos
    VALID_ROLES = {"CEO", "Administrativo", "Gerente", "Técnico"}
    
    def __init__(self, nome_usuario: str, cargo: str, conexao):
        super().__init__()
        self.setWindowIcon(QIcon('main/imagens/icone.ico'))
        
        # Validação de entrada
        if not self._validate_inputs(nome_usuario, cargo):
            return
            
        self.nome_usuario = nome_usuario
        self.cargo = cargo
        self.conexao = conexao
        
        # Cache para páginas
        self.pages: Dict[str, QWidget] = {}
        self.lista_botoes_sidebar: List[QPushButton] = []
        # CORREÇÃO: Dicionário para mapear botões com seus identificadores
        self.button_identifiers: Dict[QPushButton, str] = {}
        self.solicitacoes = []
        
        # Timer para debounce de operações
        self.refresh_timer = QTimer()
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.timeout.connect(self._perform_refresh)
        
        # CORREÇÃO: Inicializa sidebar_widget antes de qualquer uso
        self.sidebar_widget = QWidget()
        self.sidebar_widget.setObjectName("sidebarWidget")
        self.sidebar_widget.setMaximumWidth(0)  # Inicialmente fechada
        
        try:
            self._setup_window()
            self._setup_ui_components()
            self._setup_layouts()
            self._setup_animations()
            self._connect_signals()
            self._load_initial_data()
            self._apply_role_permissions()
            
            logger.info(f"MainWindow inicializada para usuário: {nome_usuario}, cargo: {cargo}")
            
        except Exception as e:
            logger.error(f"Erro na inicialização da MainWindow: {e}")
            self._show_error_message("Erro na inicialização", str(e))

    def _validate_inputs(self, nome_usuario: str, cargo: str) -> bool:
        """Valida os parâmetros de entrada"""
        if not nome_usuario or not nome_usuario.strip():
            self._show_error_message("Erro", "Nome de usuário inválido")
            return False
            
        if cargo not in self.VALID_ROLES:
            self._show_error_message("Erro", f"Cargo inválido: {cargo}")
            return False
            
        return True

    def _setup_window(self):
        """Configura propriedades básicas da janela"""
        self.setObjectName("principal_page")
        self.resize(1100, 800)
        self.setMinimumSize(1100, 800)
        
        # Instala event filter
        QApplication.instance().installEventFilter(self)

    def _setup_ui_components(self):
        """Configura todos os componentes da UI"""
        self._create_header_components()
        self._create_sidebar_components()
        self._create_content_area()

    def _create_header_components(self):
        """Cria componentes do cabeçalho"""
        # Botão refresh
        self.refresh_button = self._create_icon_button(
            "atualizar.png", self.BUTTON_SIZE, self.ICON_SIZE,
            "Atualizar interface", "refreshButton"
        )
        self.refresh_button.setProperty("role", "refresh")
        
        # Toggle button
        self.toggle_button = self._create_icon_button(
            "lateral.png", self.BUTTON_SIZE, (24, 24),
            "Menu lateral", "toggleButton"
        )
        self.toggle_button.setProperty("role", "toggle")
        
        # Logo
        self.label_logo_top = self._create_logo_label()
        
        # Título
        self.label_titulo = QLabel("Projetos")
        self.label_titulo.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter)
        
        # Avatar do usuário
        self.user_avatar = self._create_user_avatar()

    def _create_icon_button(self, icon_name: str, button_size: tuple, 
                           icon_size: tuple, tooltip: str, object_name: str) -> QPushButton:
        """Cria botão com ícone de forma padronizada"""
        button = QPushButton()
        button.setFixedSize(*button_size)
        button.setIconSize(QSize(*icon_size))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(tooltip)
        button.setObjectName(object_name)
        
        # Carrega ícone
        icon_path = self._get_image_path(icon_name)
        if icon_path:  # Verifica se o caminho é válido
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                button.setIcon(QIcon(pixmap))
            else:
                logger.warning(f"Não foi possível carregar ícone: {icon_name}")
        else:
            logger.warning(f"Caminho inválido para ícone: {icon_name}")
            
        return button

    def _create_logo_label(self) -> QLabel:
        """Cria label do logo"""
        label = QLabel()
        logo_path = self._get_image_path("tw-logotipo.png")
        
        if logo_path:
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                label.setPixmap(pixmap)
                label.setScaledContents(True)
            else:
                logger.warning("Não foi possível carregar o logo")
        else:
            logger.warning("Caminho inválido para o logo")
            
        label.setStyleSheet("background-color: none")
        label.setFixedSize(50, 50)
        return label

    def _create_user_avatar(self) -> QPushButton:
        """Cria avatar do usuário"""
        initial = self.nome_usuario[0].upper() if self.nome_usuario else "TW"
        avatar = QPushButton(initial)
        avatar.setFixedSize(*self.BUTTON_SIZE)


        avatar.setObjectName("userAvatar")
        
        # Menu de contexto
        user_menu = QMenu()
        user_menu.addAction("Sair")
        avatar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        avatar.customContextMenuRequested.connect(
            lambda pos: user_menu.exec(avatar.mapToGlobal(pos))
        )
        
        return avatar

    def _create_sidebar_components(self):
        """Cria componentes da sidebar"""
        self.sidebar_layout = QVBoxLayout()
        self.sidebar_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar_layout.setSpacing(28)  # Espaçamento maior entre os botões
        

        
        sidebar_buttons = [
            ("OS", "OS.png", self.load_OS, "btnOS"),
            ("Resumo", "Projetos.png", self.load_resumo, "btnResumo"),
            ("Gráficos", "grafico.png", self.load_grafico, "btnGraficos"),
            ("Usuários", "usuarios.png", self.load_usuarios, "btnUsuarios"),
            ("Configurações", "Configuraçoes.png", self.load_config_page, "btnConfiguracoes"),
            ("Abrir OS", "Projetos.png", self.load_abrir_os, "btnAbrirOS"),
        ]
        
        for text, icon_name, callback, object_name in sidebar_buttons:
            button = self._create_sidebar_button(text, icon_name)
            button.setObjectName(object_name)
            button.clicked.connect(callback)
            self.button_identifiers[button] = text
            self.lista_botoes_sidebar.append(button)
            self.sidebar_layout.addWidget(button)
        
        # Adiciona botão para Status OS
        btn_status_os = self._create_sidebar_button("Status OS", "status.png")
        btn_status_os.clicked.connect(lambda: self.content_area.setCurrentWidget(self.status_os_page))
        self.sidebar_layout.addWidget(btn_status_os)
        self.lista_botoes_sidebar.append(btn_status_os)

        self.sidebar_widget.setLayout(self.sidebar_layout)

    def _create_sidebar_button(self, text: str, icon_name: str) -> QPushButton:
        """Cria botão da sidebar de forma padronizada"""
        button = QPushButton()
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setMinimumHeight(100)
        button.setMinimumWidth(135)
        button.setMaximumWidth(200)
        button.setProperty("role", "sidebar")
        
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(7)  # Espaço maior entre ícone e texto
        container_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
   
        
        icon_path = self._get_image_path(icon_name)
        if icon_path:
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                target_size = 35
                scaled_pixmap = pixmap.scaled(target_size, target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                icon_label = QLabel()
                icon_label.setPixmap(scaled_pixmap)
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                icon_label.setStyleSheet("background: transparent;")
                icon_label.setFixedSize(target_size, target_size)
                container_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignHCenter)
            else:
                logger.warning(f"Não foi possível carregar ícone: {icon_name}")
        else:
            logger.warning(f"Caminho inválido para ícone: {icon_name}")
        
        text_label = QLabel(text)
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label.setWordWrap(False)  # Não quebrar linha
        text_label.setMaximumWidth(140)  # Aumenta largura máxima
        text_label.setStyleSheet("color: #0074D9; font-weight: bold;")
        text_label.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)
        container_layout.addWidget(text_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        button.setLayout(container_layout)
        return button

    def _create_content_area(self):
        """Cria área de conteúdo"""
        self.content_area = QStackedWidget()
        # Página padrão personalizada
        bem_vindo_text = f"Bem-vindo, {self.nome_usuario} ({self.cargo})"
        self.default_page = QLabel(bem_vindo_text)
        self.default_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_area.addWidget(self.default_page)
        # Adiciona a página de status das OS
        self.status_os_page = StatusOSPage(self)
        self.content_area.addWidget(self.status_os_page)

    def _setup_layouts(self):
        """Configura layouts"""
        # Status de conexão
        self.status_conexao_layout = QHBoxLayout()
        self.status_conexao_label = QLabel()
        self.status_conexao_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.btn_reconectar = QPushButton("Reconectar")
        self.btn_reconectar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reconectar.setVisible(False)
        self.btn_reconectar.clicked.connect(self._on_reconectar_clicked)
        self.status_conexao_layout.addWidget(self.status_conexao_label)
        self.status_conexao_layout.addWidget(self.btn_reconectar)
        self.status_conexao_layout.addStretch(1)
        self._atualizar_status_conexao()
        # Timer para atualizar status de conexão a cada 20 segundos
        self.timer_status_conexao = QTimer(self)
        self.timer_status_conexao.timeout.connect(self._atualizar_status_conexao)
        self.timer_status_conexao.start(20000)  # 20 segundos
        
        # Layout do cabeçalho
        self.top_layout = QHBoxLayout()
        self.top_layout.addWidget(self.toggle_button)
        self.top_layout.addWidget(self.label_logo_top)
        self.top_layout.addWidget(self.label_titulo, stretch=1)
        self.top_layout.addWidget(self.refresh_button)
        self.top_layout.addWidget(self.user_avatar)
        
        # Layout principal horizontal
        self.layout_principal = QHBoxLayout()
        self.layout_principal.addWidget(self.sidebar_widget, 0)
        self.layout_principal.addWidget(self.content_area, 1)
        self.layout_principal.setContentsMargins(0, 0, 0, 0)
        self.layout_principal.setSpacing(0)
        
        # Container principal
        self.container_widget = QWidget()
        self.container_widget.setLayout(self.layout_principal)
        
        # Layout principal vertical
        self.main_layout = QVBoxLayout()
        self.main_layout.addLayout(self.status_conexao_layout)
        self.main_layout.addLayout(self.top_layout)
        self.main_layout.addWidget(self.container_widget)
        
        # Widget central
        central_widget = QWidget()
        central_widget.setLayout(self.main_layout)
        self.setCentralWidget(central_widget)

    def _setup_animations(self):
        """Configura animações"""
        self.sidebar_animation = QPropertyAnimation(self.sidebar_widget, b"maximumWidth")
        self.sidebar_animation.setDuration(self.ANIMATION_DURATION)

    def _connect_signals(self):
        """Conecta todos os sinais"""
        self.toggle_button.clicked.connect(self.toggle_sidebar)
        self.refresh_button.clicked.connect(self.request_refresh)

        self.content_area.currentChanged.connect(self._on_page_changed)
        
        # Event filters
        self.installEventFilter(self)
        self.container_widget.installEventFilter(self)
        self.content_area.installEventFilter(self)

    def _load_initial_data(self):
        """Carrega dados iniciais"""
        try:
            self.solicitacoes = load_solicitacoes() or []
            self._update_usuarios_badge()
            # Chama notificação ao abrir o software
            self._notificar_solicitacoes_ceo()
        except Exception as e:
            logger.error(f"Erro ao carregar solicitações: {e}")
            self.solicitacoes = []

    def _apply_role_permissions(self):
        """CORREÇÃO: Aplica permissões baseadas no cargo de forma mais robusta"""
        # Definição das permissões por cargo
        permissions = {
            "CEO": {"hide": []},  # CEO vê tudo
            "Administrativo": {"hide": ["Usuários", "Resumo", "Gráficos"]},
            "Gerente": {"hide": ["Usuários", "Resumo", "Gráficos","OS"]},
            "Técnico": {"hide": ["Usuários", "Resumo", "Gráficos","OS"]}
        }
        
        logger.info(f"Aplicando permissões para cargo: {self.cargo}")
        
        if self.cargo in permissions:
            hidden_buttons = permissions[self.cargo]["hide"]
            logger.info(f"Botões que devem ser ocultados: {hidden_buttons}")
            
            for button in self.lista_botoes_sidebar:
                # CORREÇÃO: Usa o mapeamento direto ao invés de extrair texto do layout
                button_identifier = self.button_identifiers.get(button, "")
                
                if button_identifier in hidden_buttons:
                    logger.info(f"Ocultando botão: {button_identifier}")
                    button.hide()
                    button.setVisible(False)
                    # Remove também do layout para não ocupar espaço
                    self.sidebar_layout.removeWidget(button)
                else:
                    logger.info(f"Mantendo botão visível: {button_identifier}")
                    button.show()
                    button.setVisible(True)
        else:
            logger.warning(f"Cargo não reconhecido: {self.cargo}")

    def _get_button_text(self, button: QPushButton) -> str:
        """CORREÇÃO: Método alternativo usando o mapeamento direto"""
        return self.button_identifiers.get(button, "")

    def _get_image_path(self, filename: str) -> str:
        """Retorna caminho absoluto para imagem"""
        try:
            # Constrói o caminho absoluto
            path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), '..', 'imagens', filename)
            )
            # Garante que retorna uma string
            return str(path)
        except Exception as e:
            logger.error(f"Erro ao obter caminho da imagem {filename}: {e}")
            return ""

    def _update_usuarios_badge(self):
        """Atualiza badge de usuários e ícone do menu lateral"""
        try:
            count = len(self.solicitacoes)
            badge = " ●" if count > 0 else ""
            # Notificação para CEO se houver solicitações
            if badge and getattr(self, 'cargo', '').upper() == 'CEO':
                try:
                    if QSystemTrayIcon.isSystemTrayAvailable():
                        tray = getattr(self, '_notificacao_tray', None)
                        if tray is None:
                            tray = QSystemTrayIcon(self)
                            tray.setVisible(True)
                            self._notificacao_tray = tray
                        tray.showMessage(
                            "Solicitações pendentes",
                            "Há solicitações de usuários aguardando aprovação.",
                            QSystemTrayIcon.MessageIcon.Information,
                            7000
                        )
                except Exception as e:
                    logger.error(f"Erro ao exibir notificação: {e}")
            # Troca o ícone do botão Usuários
            for button in self.lista_botoes_sidebar:
                if button.objectName() == "btnUsuarios":
                    layout = button.layout()
                    if layout:
                        for i in range(layout.count()):
                            widget = layout.itemAt(i).widget()
                            if isinstance(widget, QLabel) and widget.pixmap():
                                # Troca o ícone
                                from PyQt6.QtGui import QPixmap
                                icon_file = "Notificaçoes.png" if badge else "usuarios.png"
                                icon_path = self._get_image_path(icon_file)
                                pixmap = QPixmap(icon_path)
                                if not pixmap.isNull():
                                    target_size = 35
                                    scaled_pixmap = pixmap.scaled(target_size, target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                                    widget.setPixmap(scaled_pixmap)
                                break
            # Atualiza texto do badge
            for button in self.lista_botoes_sidebar:
                if button.objectName() == "btnUsuarios":
                    layout = button.layout()
                    if layout:
                        for i in range(layout.count()):
                            widget = layout.itemAt(i).widget()
                            if isinstance(widget, QLabel) and not widget.pixmap():
                                original_text = widget.text().replace(" ●", "")
                                widget.setText(original_text + badge)
                                break
                    break
        except Exception as e:
            logger.error(f"Erro ao atualizar badge de usuários: {e}")

    def request_refresh(self):
        """Solicita refresh com debounce"""
        self.refresh_timer.start(500)  # 500ms debounce

    def _perform_refresh(self):
        """Executa refresh da interface"""
        try:
            self._atualizar_status_conexao()
            self.close_sidebar_if_open()
            # Remove todas as páginas exceto a padrão
            pages_to_remove = list(self.pages.keys())
            for page_name in pages_to_remove:
                if page_name in self.pages:
                    widget = self.pages[page_name]
                    self.content_area.removeWidget(widget)
                    widget.deleteLater()
                    del self.pages[page_name]
            # Recarrega dados
            self._load_initial_data()
            # Volta para página inicial
            self.update_title("Projetos")
            self.content_area.setCurrentWidget(self.default_page)
            # CORREÇÃO: Reaplica permissões após refresh
            self._apply_role_permissions()
            # Chama notificação ao atualizar
            self._notificar_solicitacoes_ceo()
            # Atualiza a aba de status das OS
            if hasattr(self, 'status_os_page'):
                self.status_os_page.refresh()
            logger.info("Interface atualizada com sucesso")
        except Exception as e:
            logger.error(f"Erro durante refresh: {e}")
            self._show_error_message("Erro", f"Erro ao atualizar interface: {e}")

    def toggle_sidebar(self):
        """Alterna visibilidade da sidebar"""
        try:
            current_width = self.sidebar_widget.maximumWidth()
            
            if current_width > 0:
                self.sidebar_animation.setStartValue(current_width)
                self.sidebar_animation.setEndValue(0)
            else:
                self.sidebar_animation.setStartValue(0)
                self.sidebar_animation.setEndValue(self.SIDEBAR_WIDTH)
            
            # Desconecta sinais anteriores
            try:
                self.sidebar_animation.finished.disconnect()
            except TypeError:
                pass
                
            self.sidebar_animation.finished.connect(
                lambda: self._adjust_sidebar_buttons(self.sidebar_widget.maximumWidth())
            )
            
            self.sidebar_animation.start()
            
        except Exception as e:
            logger.error(f"Erro ao alternar sidebar: {e}")

    def close_sidebar_if_open(self):
        """Fecha sidebar se estiver aberta"""
        if self.sidebar_widget.maximumWidth() > 0:
            self.sidebar_animation.setStartValue(self.sidebar_widget.width())
            self.sidebar_animation.setEndValue(0)
            self.sidebar_animation.start()

    def _adjust_sidebar_buttons(self, sidebar_width: int):
        """Ajusta visibilidade dos textos dos botões baseado na largura"""
        show_text = sidebar_width > 100
        
        for button in self.lista_botoes_sidebar:
            # CORREÇÃO: Só ajusta botões que estão visíveis
            if button.isVisible():
                layout = button.layout()
                if layout:
                    for i in range(layout.count()):
                        widget = layout.itemAt(i).widget()
                        if isinstance(widget, QLabel) and not widget.pixmap():
                            widget.setVisible(show_text)

    def eventFilter(self, source, event):
        """Filtro de eventos para fechar sidebar"""
        if event.type() == QEvent.Type.MouseButtonPress:
            try:
                pos = event.globalPosition().toPoint()
                rect = self.sidebar_widget.geometry()
                top_left = self.sidebar_widget.mapToGlobal(QPoint(0, 0))
                rect.moveTopLeft(top_left)
                
                if not rect.contains(pos):
                    self.close_sidebar_if_open()
            except Exception as e:
                logger.error(f"Erro no event filter: {e}")
                
        return super().eventFilter(source, event)

    def _on_page_changed(self, index: int):
        """Callback quando página muda no QStackedWidget"""
        try:
            page = self.content_area.currentWidget()
            if page is None:
                return

            # Configura tabelas para expandir corretamente
            for table in page.findChildren((QTableView, QTableWidget)):
                table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                header = table.horizontalHeader()
                if header:
                    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
                    
        except Exception as e:
            logger.error(f"Erro ao mudar página: {e}")

    def update_title(self, title: str):
        """Atualiza título da janela"""
        self.label_titulo.setText(title)

    def _create_or_get_page(self, page_name: str, page_class, *args, **kwargs):
        """Cria ou retorna página existente do cache, com indicador de carregamento para páginas pesadas"""
        if page_name not in self.pages:
            try:
                # Mostra indicador de carregamento para páginas pesadas
                if page_class.__name__ in ["CadastrarOSPage", "Resumo", "TelaUsuarios", "EditarOSPage"]:
                    progress = QProgressDialog(f"Carregando {page_name}...", None, 0, 0, self)
                    progress.setWindowTitle("Aguarde")
                    progress.setWindowModality(Qt.WindowModality.ApplicationModal)
                    progress.setMinimumDuration(0)
                    progress.setCancelButton(None)
                    progress.show()
                    QApplication.processEvents()
                else:
                    progress = None
                
                self.pages[page_name] = page_class(*args, **kwargs)
                self.content_area.addWidget(self.pages[page_name])
                logger.info(f"Página '{page_name}' criada e adicionada ao cache")
                if progress:
                    progress.close()
            except Exception as e:
                logger.error(f"Erro ao criar página '{page_name}': {e}")
                self._show_error_message("Erro", f"Erro ao carregar página {page_name}")
                return None
                
        return self.pages[page_name]

    # Métodos de carregamento de páginas
    def load_OS(self):
        """Carrega página de OS"""
        self.update_title("OS")
        page = self._create_or_get_page('OS', CadastrarOSPage, self)
        if page:
            self.content_area.setCurrentWidget(page)

    def load_usuarios(self):
        """Carrega página de usuários"""
        self.update_title("Usuários")
        page = self._create_or_get_page('Usuarios', TelaUsuarios)
        if page:
            self.content_area.setCurrentWidget(page)
            self._update_usuarios_badge()

    def load_resumo(self):
        """Carrega página de resumo"""
        self.update_title("Resumo")
        page = self._create_or_get_page('Resumo', Resumo)
        if page:
            self.content_area.setCurrentWidget(page)

    def load_abrir_os(self):
        """Carrega página de abrir OS"""
        self.update_title("Abrir OS")
        page = self._create_or_get_page('AbrirOS', AbrirOSPage, self)
        if page:
            self.content_area.setCurrentWidget(page)

    def load_config_page(self):
        """Carrega página de configurações"""
        self.update_title("Configurações")
        page = self._create_or_get_page(
            'Configuracoes', ConfiguracoesUsuarioDialog,
            parent=self
        )
        if page:
            self.content_area.setCurrentWidget(page)

    def load_grafico(self):
        """Carrega página de gráficos"""
        self.update_title("Gráficos")
        page = self._create_or_get_page('Graficos', TelaGraficos, parent=self)
        if page:
            self.content_area.setCurrentWidget(page)

    def load_perfil(self):
        exit ()  

    def atualizar_avatar_topo(self, image_path: str):
        """Atualiza avatar no topo da janela"""
        try:
            if os.path.exists(image_path):
                pixmap = ImageCache.get_pixmap(image_path, self.BUTTON_SIZE)
                if pixmap:
                    self.user_avatar.setIcon(QIcon(pixmap))
                    self.user_avatar.setText("")
        except Exception as e:
            logger.error(f"Erro ao atualizar avatar: {e}")

    def _show_error_message(self, title: str, message: str):
        """Mostra mensagem de erro"""
        try:
            QtWidgets.QMessageBox.critical(self, title, message)
        except Exception as e:
            logger.error(f"Erro ao mostrar mensagem: {e}")

    def retranslateUi(self, Dialog):
        """Tradução da UI"""
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "Menu"))

    def closeEvent(self, event):
        """Evento de fechamento da janela"""
        try:
            # Limpa cache de imagens
            ImageCache.clear()
            
            # Remove event filters
            QApplication.instance().removeEventFilter(self)
            
            logger.info("MainWindow fechada corretamente")
            event.accept()
        except Exception as e:
            logger.error(f"Erro ao fechar MainWindow: {e}")
            event.accept()

    def _notificar_solicitacoes_ceo(self):
        """Notifica CEO sobre solicitações pendentes ao abrir ou atualizar."""
        try:
            count = len(self.solicitacoes)
            if count > 0 and getattr(self, 'cargo', '').upper() == 'CEO':
                from PyQt6.QtWidgets import QSystemTrayIcon
                if QSystemTrayIcon.isSystemTrayAvailable():
                    tray = getattr(self, '_notificacao_tray', None)
                    if tray is None:
                        tray = QSystemTrayIcon(self)
                        tray.setVisible(True)
                        self._notificacao_tray = tray
                    tray.showMessage(
                        "Solicitações pendentes",
                        "Há solicitações de usuários aguardando aprovação.",
                        QSystemTrayIcon.MessageIcon.Information,
                        7000
                    )
        except Exception as e:
            logger.error(f"Erro ao notificar CEO: {e}")

    def _atualizar_status_conexao(self):
        if health_check():
            self.status_conexao_label.setText("<span style='color: #1ec700;'>✔ Conectado ao banco de dados</span>")
            self.btn_reconectar.setVisible(False)
        else:
            self.status_conexao_label.setText("<span style='color: #c70000;'>✖ Desconectado do banco de dados</span>")
            self.btn_reconectar.setVisible(True)

    def _on_reconectar_clicked(self):
        self.status_conexao_label.setText("Reconectando...")
        QApplication.processEvents()
        try:
            conectar_banco()
        except Exception:
            pass
        self._atualizar_status_conexao()