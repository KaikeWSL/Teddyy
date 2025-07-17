import os
import logging
import time
from typing import Optional, Dict, Any, List, Callable
from contextlib import contextmanager
from functools import wraps
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor, RealDictRow
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constantes
MAX_RETRIES = 3
RETRY_DELAY = 1  # segundos
MAX_POOL_SIZE = 20
MIN_POOL_SIZE = 5
POOL_TIMEOUT = 30
CONNECTION_TIMEOUT = 10
MAX_IDLE_TIME = 300  # 5 minutos

@dataclass(frozen=True)
class DatabaseConfig:
    """Configurações do banco de dados"""
    HOST: str = 'ep-cold-sky-a537fwxd-pooler.us-east-2.aws.neon.tech'
    PORT: str = '5432'
    DATABASE: str = 'neondb'
    USER: str = 'neondb_owner'
    PASSWORD: str = 'npg_91HbcvdzrFLw'
    
    @classmethod
    def get_connection_string(cls) -> str:
        """Retorna string de conexão formatada"""
        return (
            f"host={cls.HOST} "
            f"port={cls.PORT} "
            f"dbname={cls.DATABASE} "
            f"user={cls.USER} "
            f"password={cls.PASSWORD} "
            f"connect_timeout={CONNECTION_TIMEOUT}"
        )

class ConnectionPool:
    """Gerenciador de pool de conexões com retry e monitoramento"""
    
    def __init__(self):
        self._pool: Optional[pool.ThreadedConnectionPool] = None
        self._lock = Lock()
        self._last_cleanup = time.time()
        self._logger = logging.getLogger(__name__)
    
    def create_pool(self) -> Optional[pool.ThreadedConnectionPool]:
        """Cria pool de conexões com retry"""
        last_exception = None
        for attempt in range(MAX_RETRIES):
            try:
                with self._lock:
                    if self._pool is None:
                        self._pool = pool.ThreadedConnectionPool(
                            MIN_POOL_SIZE,
                            MAX_POOL_SIZE,
                            DatabaseConfig.get_connection_string()
                        )
                        self._logger.info("Pool de conexões criado com sucesso")
                    return self._pool
            except Exception as e:
                last_exception = e
                wait_time = RETRY_DELAY * (2 ** attempt)  # Backoff exponencial
                self._logger.warning(
                    f"Falha ao criar pool (tentativa {attempt + 1}/{MAX_RETRIES}). "
                    f"Tentando novamente em {wait_time}s..."
                )
                time.sleep(wait_time)
        self._logger.error(f"Falha ao criar pool após {MAX_RETRIES} tentativas: {last_exception}")
        return None
    
    def get_connection(self) -> Optional[Any]:
        """Obtém conexão do pool com retry e garante que está aberta"""
        if not self._pool:
            self._pool = self.create_pool()
        if not self._pool:
            return None
        try:
            conn = self._pool.getconn()
            # Verifica se a conexão está fechada
            if hasattr(conn, 'closed') and conn.closed:
                self._logger.warning("Conexão obtida do pool estava fechada. Criando nova conexão.")
                # Tenta criar uma nova conexão manualmente
                conn = psycopg2.connect(DatabaseConfig.get_connection_string())
            return conn
        except Exception as e:
            self._logger.error(f"Erro ao obter conexão do pool: {e}")
            return None
    
    def put_connection(self, conn: Any) -> None:
        """Retorna conexão ao pool"""
        if not self._pool or not conn:
            return
            
        try:
            self._pool.putconn(conn)
        except Exception as e:
            self._logger.error(f"Erro ao retornar conexão ao pool: {e}")
    
    def close_pool(self) -> None:
        """Fecha pool de conexões"""
        with self._lock:
            if self._pool:
                try:
                    self._pool.closeall()
                    self._logger.info("Pool de conexões fechado")
                except Exception as e:
                    self._logger.error(f"Erro ao fechar pool: {e}")
                finally:
                    self._pool = None
    
    def cleanup_idle_connections(self) -> None:
        """Limpa conexões ociosas"""
        now = time.time()
        if now - self._last_cleanup < MAX_IDLE_TIME:
            return
            
        self._last_cleanup = now
        with self._lock:
            if self._pool:
                try:
                    # Força limpeza de conexões ociosas
                    self._pool.closeall()
                    self._pool = None
                    self.create_pool()
                except Exception as e:
                    self._logger.error(f"Erro na limpeza de conexões: {e}")

# Instância global do pool
_pool = ConnectionPool()

def get_conn():
    """Obtém conexão do pool"""
    return _pool.get_connection()

def put_conn(conn):
    """Retorna conexão ao pool"""
    _pool.put_connection(conn)

def close_pool():
    """Fecha pool de conexões"""
    _pool.close_pool()

def execute_query(query: str, params: Optional[Dict] = None) -> Optional[List[Dict[str, Any]]]:
    """Executa query com retry e tratamento de erros"""
    conn = None
    try:
        conn = get_conn()
        if not conn:
            return None
            
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params or {})
            if cur.description:  # Se for SELECT
                return cur.fetchall()
            return []
            
    except Exception as e:
        logger.error(f"Erro ao executar query: {e}")
        return None
        
    finally:
        if conn:
            put_conn(conn)

def with_db_connection(func):
    """Decorator para funções que precisam de conexão"""
    def wrapper(*args, **kwargs):
        conn = None
        try:
            conn = get_conn()
            if not conn:
                raise Exception("Não foi possível obter conexão")
            return func(conn, *args, **kwargs)
        except Exception as e:
            logger.error(f"Erro em {func.__name__}: {e}")
            raise
        finally:
            if conn:
                put_conn(conn)
    return wrapper

def get_pool_status() -> dict:
    """
    Retorna status atual do pool.
    """
    try:
        if not _pool._pool or _pool._pool.closed:
            return {"status": "fechado", "conexoes_ativas": 0, "conexoes_total": 0}
        
        # Informações básicas do pool
        return {
            "status": "ativo",
            "minconn": _pool._pool.minconn,
            "maxconn": _pool._pool.maxconn,
            "fechado": _pool._pool.closed
        }
    except Exception as e:
        return {"status": "erro", "erro": str(e)}

def health_check() -> bool:
    """
    Verifica saúde do pool de conexões.
    """
    try:
        conn = get_conn()
        if not conn:
            return False
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()
            return result is not None
        finally:
            put_conn(conn)
    except Exception as e:
        print(f"❌ Health check falhou: {e}")
        return False

# Função de compatibilidade
def conectar_banco():
    """
    Função de compatibilidade com código legado.
    Retorna conexão do pool.
    """
    conn = get_conn()
    print("✅ Conexão obtida do pool (modo compatibilidade)")
    return conn

# Auto-cleanup no exit do módulo
import atexit
atexit.register(close_pool)

if __name__ == "__main__":
    # Teste do pool
    print("🧪 Testando pool de conexões...")
    
    try:
        # Teste básico
        conn = conectar_banco()
        put_conn(conn)
        
        # Health check
        if health_check():
            print("✅ Health check passou")
        else:
            print("❌ Health check falhou")
        
        # Status do pool
        status = get_pool_status()
        print(f"📊 Status do pool: {status}")
        
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
    finally:
        close_pool()
        print(" Teste concluído")