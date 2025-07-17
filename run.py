import sys
import os
import atexit
import logging
from pathlib import Path
from functools import lru_cache
from typing import Optional, Callable
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer, Qt, QObject, pyqtSignal
from PyQt6.QtGui import QIcon
import subprocess
import platform

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Imports locais
from main.frontend.splash_screen import SplashScreen
from main.backend.conexao import conectar_db
from main.backend.db_connection import close_pool
from main.frontend.tela_login import TelaLogin
from main.frontend.main_window import MainWindow

def get_motherboard_serial() -> str:
    """
    Obtém o serial da placa-mãe do sistema.
    """
    try:
        system = platform.system()
        
        if system == "Windows":
            # Windows: usa wmic para obter o serial da placa-mãe
            result = subprocess.run(
                ["wmic", "baseboard", "get", "serialnumber", "/value"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.startswith('SerialNumber='):
                        serial = line.split('=', 1)[1].strip()
                        if serial and serial.upper() not in ['', 'TO BE FILLED BY O.E.M.', 'NOT SPECIFIED']:
                            return serial
                        
            # Fallback: tenta obter UUID da placa-mãe
            result = subprocess.run(
                ["wmic", "baseboard", "get", "product", "/value"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.startswith('Product='):
                        product = line.split('=', 1)[1].strip()
                        if product and product.upper() not in ['', 'TO BE FILLED BY O.E.M.', 'NOT SPECIFIED']:
                            return product
                            
        elif system == "Linux":
            # Linux: tenta diferentes métodos para obter o serial
            commands = [
                ["dmidecode", "-s", "baseboard-serial-number"],
                ["dmidecode", "-s", "baseboard-product-name"],
                ["cat", "/sys/class/dmi/id/board_serial"],
                ["cat", "/sys/class/dmi/id/product_serial"]
            ]
            
            for cmd in commands:
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        serial = result.stdout.strip()
                        if serial and serial.upper() not in ['', 'TO BE FILLED BY O.E.M.', 'NOT SPECIFIED']:
                            return serial
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    continue
                    
        elif system == "Darwin":  # macOS
            # macOS: usa system_profiler
            result = subprocess.run(
                ["system_profiler", "SPHardwareDataType"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'Serial Number' in line:
                        serial = line.split(':', 1)[1].strip()
                        if serial:
                            return serial
                            
        # Se nenhum método funcionou, gera um identificador baseado no hostname
        import socket
        hostname = socket.gethostname()
        logger.warning(f"Não foi possível obter serial da placa-mãe, usando hostname: {hostname}")
        return f"HOST_{hostname}"
        
    except Exception as e:
        logger.error(f"Erro ao obter serial da placa-mãe: {e}")
        # Fallback final
        import socket
        hostname = socket.gethostname()
        return f"HOST_{hostname}"

def check_serial_autorizado(serial: str) -> bool:
    """Verifica se o serial da placa-mãe está autorizado na tabela 'autorizados'."""
    from main.backend.db_connection import get_conn, put_conn
    conn = None
    try:
        conn = get_conn()
        if not conn:
            logger.error("Não foi possível obter conexão com banco para verificar licença")
            return False
            
        cur = conn.cursor()
        cur.execute('SELECT 1 FROM autorizados WHERE serial_placa_mae = %s', (serial,))
        autorizado = cur.fetchone() is not None
        cur.close()
        
        logger.info(f"Verificação de licença para serial '{serial}': {'AUTORIZADO' if autorizado else 'NÃO AUTORIZADO'}")
        return autorizado
        
    except Exception as e:
        logger.error(f'Erro ao verificar autorização do serial: {e}')
        return False
    finally:
        if conn:
            put_conn(conn)

def verificar_licenca() -> bool:
    """
    Verifica se a máquina atual possui licença para executar o sistema.
    """
    try:
        logger.info("Iniciando verificação de licença...")
        
        # Obtém o serial da placa-mãe
        serial = get_motherboard_serial()
        logger.info(f"Serial da placa-mãe detectado: {serial}")
        
        # Verifica se está autorizado
        if check_serial_autorizado(serial):
            logger.info("✅ Licença válida - Sistema autorizado")
            return True
        else:
            logger.warning("❌ Licença inválida - Sistema não autorizado")
            return False
            
    except Exception as e:
        logger.error(f"Erro crítico na verificação de licença: {e}")
        return False

def show_license_error():
    """
    Mostra mensagem de erro de licença para o usuário.
    """
    try:
        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)
            
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("Licença Inválida")
        msg.setText("Sistema não autorizado para esta máquina.")
        msg.setInformativeText("Entre em contato com o administrador para obter uma licença válida.")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
        
    except Exception as e:
        logger.error(f"Erro ao mostrar diálogo de licença: {e}")
        print("ERRO: Sistema não autorizado para esta máquina.")
        print("Entre em contato com o administrador para obter uma licença válida.")

# Hook global para exceções não tratadas
def excecao_nao_tratada(exctype, value, traceback):
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setWindowTitle("Erro Crítico")
    msg.setText(f"Ocorreu um erro inesperado:\n{value}")
    msg.exec()
    # Loga o erro
    logging.critical("Erro não tratado", exc_info=(exctype, value, traceback))

sys.excepthook = excecao_nao_tratada

class ApplicationManager(QObject):
    """
    Gerenciador central da aplicação com controle de estado e recursos.
    """
    main_window_ready = pyqtSignal(object)  # Sinal quando MainWindow está pronta
    
    def __init__(self):
        super().__init__()
        self.app: Optional[QApplication] = None
        self.main_window: Optional[MainWindow] = None
        self.splash: Optional[SplashScreen] = None
        self.login_window: Optional[TelaLogin] = None
        self.database_connection = None
        
    def setup_application(self) -> Optional[QApplication]:
        """
        Configura aplicação PyQt6 com todas as otimizações necessárias.
        """
        try:
            # Cria aplicação se não existe
            app_instance = QApplication.instance()
            if not app_instance:
                self.app = QApplication(sys.argv)
                logger.info("Nova instância do QApplication criada")
            elif isinstance(app_instance, QApplication):
                self.app = app_instance
                logger.info("Usando instância existente do QApplication")
            else:
                logger.error("A instância existente não é um QApplication.")
                self.app = None

            # Configurações de aplicação
            if self.app is not None:
                self.app.setApplicationName("Sistema de OS")
                self.app.setApplicationVersion("1.0.0")
                self.app.setOrganizationName("Sua Empresa")
            else:
                logger.warning("QApplication não está inicializado ao definir propriedades da aplicação")
            
            # Configurações de High DPI (PyQt6)
            try:
                if self.app is not None:
                    attr = getattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps", None)
                    if attr is not None:
                        self.app.setAttribute(attr, True)
                        logger.info("High DPI configurado")
                    else:
                        logger.info("High DPI não configurado (atributo não existe)")
                else:
                    logger.warning("QApplication não está inicializado")
            except Exception as e:
                logger.info("High DPI não configurado (ignorado)")
            
            # Configura ícone da aplicação
            self._set_application_icon()
            
            return self.app
            
        except Exception as e:
            logger.error(f"Erro ao configurar aplicação: {e}")
            raise

    def _set_application_icon(self):
        """Define ícone da aplicação se disponível."""
        try:
            icon_path = self._find_resource("icone.ico")
            if icon_path and os.path.exists(icon_path):
                if self.app is not None:
                    self.app.setWindowIcon(QIcon(icon_path))
                    logger.info("Ícone da aplicação definido")
        except Exception as e:
            logger.warning(f"Não foi possível definir ícone: {e}")

    @lru_cache(maxsize=10)
    def _find_resource(self, filename: str) -> Optional[str]:
        """
        Encontra recursos (QSS, imagens, etc.) com cache.
        """
        try:
            if getattr(sys, 'frozen', False):
                # Executável PyInstaller
                base_path = Path(sys._MEIPASS)
                for resource_file in base_path.rglob(filename):
                    return str(resource_file)
            else:
                # Modo desenvolvimento
                base_path = Path(__file__).parent
                
                # Procura em locais comuns
                search_paths = [
                    base_path / "main" / "frontend" / filename,
                    base_path / "main" / "imagens" / filename,
                    base_path / filename
                ]
                
                for path in search_paths:
                    if path.exists():
                        return str(path)
                        
                # Busca recursiva como fallback
                for resource_file in base_path.rglob(filename):
                    return str(resource_file)
                    
        except Exception as e:
            logger.error(f"Erro ao procurar recurso '{filename}': {e}")
            
        return None

    @lru_cache(maxsize=5)
    def load_stylesheet(self, filename: str = "style_global.qss") -> str:
        """
        Carrega stylesheet com cache e tratamento de erro robusto.
        """
        try:
            qss_path = self._find_resource(filename)
            if not qss_path:
                logger.warning(f"Arquivo QSS '{filename}' não encontrado")
                return ""
                
            with open(qss_path, "r", encoding="utf-8") as f:
                content = f.read()
                logger.info(f"Stylesheet '{filename}' carregado com sucesso")
                return content
                
        except FileNotFoundError:
            logger.warning(f"Arquivo QSS '{filename}' não existe")
        except UnicodeDecodeError:
            logger.error(f"Erro de codificação ao ler '{filename}'")
        except Exception as e:
            logger.error(f"Erro inesperado ao carregar QSS: {e}")
            
        return ""

    def apply_stylesheet(self):
        """
        Aplica stylesheet com fallback para estilo padrão.
        """
        try:
            stylesheet = self.load_stylesheet("style_global.qss")
            if stylesheet:
                if self.app is not None:
                    self.app.setStyleSheet(stylesheet)
                logger.info("✅ Stylesheet aplicado com sucesso")
            else:
                # Aplica estilo básico como fallback
                basic_style = """
                QMainWindow {
                    background-color: #f0f0f0;
                }
                QPushButton {
                    background-color: #e1e1e1;
                    border: 1px solid #c0c0c0;
                    padding: 5px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #d4edda;
                }
                """
                if self.app is not None:
                    self.app.setStyleSheet(basic_style)
                logger.info("✅ Estilo básico aplicado como fallback")
                
        except Exception as e:
            logger.error(f"Erro ao aplicar stylesheet: {e}")

    def initialize_database(self) -> bool:
        """
        Inicializa conexão com banco com retry e validação.
        """
        max_retries = 3
        retry_delay = 1000  # ms
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Tentativa {attempt + 1} de conexão com banco...")
                self.database_connection = conectar_db()
                
                if self.database_connection:
                    logger.info("✅ Conexão com banco estabelecida")
                    return True
                else:
                    logger.warning(f"Conexão retornou None na tentativa {attempt + 1}")
                    
            except Exception as e:
                logger.error(f"❌ Tentativa {attempt + 1} falhou: {e}")
                if attempt < max_retries - 1:
                    # Aguarda antes da próxima tentativa
                    QTimer.singleShot(retry_delay, lambda: None)
                    retry_delay *= 2  # Backoff exponencial
                    
        logger.error("❌ Falha ao conectar com banco após todas as tentativas")
        return False

    def show_error_dialog(self, title: str, message: str):
        """
        Mostra diálogo de erro para o usuário.
        """
        try:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle(title)
            msg.setText(message)
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()
        except Exception as e:
            logger.error(f"Erro ao mostrar diálogo: {e}")

    def start_splash_sequence(self, post_splash_callback: Callable[[], None]):
        """
        Inicia sequência de splash screen e, ao finalizar, executa post_splash_callback.
        """
        try:
            self.splash = SplashScreen()
            
            def on_splash_finished():
                try:
                    # Fecha e limpa referência da splash
                    self.splash.close()
                    self.splash = None
                    logger.info("Splash screen finalizado")

                    # Agora que o splash terminou, chama o callback passado
                    post_splash_callback()

                except Exception as e:
                    logger.error(f"Erro ao finalizar splash: {e}")
            
            # Conecta sinal de finalização da splash
            self.splash.finished.connect(on_splash_finished)
            
            # Inicia splash
            self.splash.start()
            logger.info("Splash screen iniciado")
            
        except Exception as e:
            logger.error(f"Erro ao iniciar splash: {e}")
            # Se falhar o splash, chama logo o callback para não travar a aplicação
            post_splash_callback()

    def create_main_window(self, nome_usuario: str, cargo: str) -> bool:
        """
        Cria janela principal com validação e tratamento de erro.
        """
        try:
            logger.info(f"Criando MainWindow para usuário: {nome_usuario}, cargo: {cargo}")
            
            # Valida parâmetros
            if not nome_usuario or not nome_usuario.strip():
                self.show_error_dialog("Erro", "Nome de usuário inválido")
                return False
                
            if not cargo or not cargo.strip():
                self.show_error_dialog("Erro", "Cargo inválido")
                return False
            
            # Cria janela principal
            self.main_window = MainWindow(nome_usuario, cargo, self.database_connection)
            
            # Conecta evento de fechamento
            self.main_window.closeEvent = self._on_main_window_close
            
            # Mostra janela
            self.main_window.show()
            self.main_window.raise_()  # Traz para frente
            self.main_window.activateWindow()  # Ativa janela
            
            # Emite sinal
            self.main_window_ready.emit(self.main_window)
            
            logger.info("✅ MainWindow criada e exibida com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar MainWindow: {e}")
            self.show_error_dialog("Erro Crítico", f"Erro ao carregar janela principal:\n{str(e)}")
            return False

    def _on_main_window_close(self, event):
        """
        Callback para fechamento da janela principal.
        """
        try:
            logger.info("MainWindow sendo fechada...")
            self.cleanup_resources()
            event.accept()
        except Exception as e:
            logger.error(f"Erro ao fechar MainWindow: {e}")
            event.accept()

    def show_login(self, main_callback: Callable[[str, str], None]):
        """
        Mostra tela de login.
        """
        try:
            self.login_window = TelaLogin(main_callback)
            self.login_window.show()
            self.login_window.raise_()
            self.login_window.activateWindow()
            logger.info("✅ Tela de login exibida")
            
        except Exception as e:
            logger.error(f"❌ Erro ao mostrar tela de login: {e}")
            self.show_error_dialog("Erro", f"Erro ao carregar tela de login:\n{str(e)}")

    def cleanup_resources(self):
        """
        Limpa todos os recursos da aplicação.
        """
        try:
            logger.info("Iniciando limpeza de recursos...")
            
            # Fecha janelas
            if self.main_window:
                self.main_window.close()
                self.main_window = None
                
            if self.login_window:
                self.login_window.close()
                self.login_window = None
                
            if self.splash:
                self.splash.close()
                self.splash = None
            
            # Fecha pool de conexões
            try:
                close_pool()
                logger.info("✅ Pool de conexões fechado")
            except Exception as e:
                logger.warning(f"Erro ao fechar pool: {e}")
            
            # Limpa cache
            self._find_resource.cache_clear()
            self.load_stylesheet.cache_clear()
            
            logger.info("✅ Recursos limpos com sucesso")
            
        except Exception as e:
            logger.error(f"Erro durante limpeza: {e}")

# Instância global do gerenciador
app_manager = ApplicationManager()

def iniciar_main(nome_usuario: str, cargo: str):
    """
    Callback para iniciar janela principal após login.
    AGORA INCLUI VERIFICAÇÃO DE LICENÇA E CONEXÃO COM BANCO.
    """
    try:
        logger.info(f"Iniciando main para: {nome_usuario} ({cargo})")
        
        # Fecha tela de login se existe
        if app_manager.login_window:
            app_manager.login_window.close()
            app_manager.login_window = None
        
        # ========================
        # VERIFICAÇÕES PÓS-LOGIN
        # ========================
        
        # 1. Inicializa conexão com banco
        logger.info("🔗 Conectando ao banco de dados...")
        if not app_manager.initialize_database():
            app_manager.show_error_dialog(
                "Erro de Conexão", 
                "Não foi possível conectar ao banco de dados.\n"
                "Verifique a configuração e tente novamente."
            )
            # Volta para tela de login
            app_manager.show_login(iniciar_main)
            return
        
        # 2. Verifica licença
        logger.info("🔐 Verificando licença do sistema...")
        if not verificar_licenca():
            show_license_error()
            logger.error("❌ Sistema encerrado - Licença inválida")
            sys.exit(1)
        
        logger.info("✅ Licença verificada com sucesso")
        
        # 3. Se tudo OK, inicia splash e depois a MainWindow
        app_manager.start_splash_sequence(lambda: app_manager.create_main_window(nome_usuario, cargo))
            
    except Exception as e:
        logger.error(f"Erro crítico em iniciar_main: {e}")
        app_manager.show_error_dialog("Erro Crítico", f"Erro ao iniciar aplicação:\n{str(e)}")
        sys.exit(1)

def setup_cleanup():
    """
    Configura limpeza automática de recursos.
    """
    def cleanup():
        try:
            app_manager.cleanup_resources()
            logger.info("Cleanup automático executado")
        except Exception as e:
            logger.error(f"Erro no cleanup automático: {e}")
    
    atexit.register(cleanup)

def setup_periodic_cleanup():
    """
    Configura limpeza periódica opcional.
    """
    cleanup_timer = QTimer()
    cleanup_timer.timeout.connect(lambda: None)  # Força garbage collection
    cleanup_timer.start(300000)  # A cada 5 minutos
    return cleanup_timer

def main():
    """
    Função principal otimizada - INTERFACE PRIMEIRO, VERIFICAÇÕES DEPOIS.
    """
    try:
        logger.info("🚀 Iniciando aplicação...")
        
        # Configura limpeza automática
        setup_cleanup()
        
        # Configura aplicação PyQt6
        app = app_manager.setup_application()
        
        # Aplica stylesheet
        app_manager.apply_stylesheet()
        
        # Configura timer de limpeza periódica
        cleanup_timer = setup_periodic_cleanup()
        
        # ===============================================
        # MOSTRA INTERFACE IMEDIATAMENTE (SEM VERIFICAÇÕES)
        # ===============================================
        logger.info("🖥️ Abrindo interface de login...")
        app_manager.show_login(iniciar_main)
        
        logger.info("✅ Aplicação configurada, iniciando loop principal...")
        
        # Executa aplicação
        exit_code = app.exec()
        logger.info(f"Aplicação encerrada com código: {exit_code}")
        
        return exit_code
        
    except KeyboardInterrupt:
        logger.info("⚠️ Aplicação interrompida pelo usuário")
        return 0
    except Exception as e:
        logger.error(f"❌ Erro crítico na aplicação: {e}")
        try:
            if 'app_manager' in locals():
                app_manager.show_error_dialog("Erro Crítico", f"Erro fatal na aplicação:\n{str(e)}")
        except:
            pass
        return 1
    finally:
        try:
            app_manager.cleanup_resources()
        except:
            pass

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)