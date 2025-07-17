import psycopg2
import hashlib
from functools import lru_cache
from typing import Optional, Dict, Any
from .db_connection import get_conn, put_conn

# Cache para credenciais verificadas recentemente
@lru_cache(maxsize=64)
def _hash_senha(senha: str) -> str:
    """Cache de hash de senhas para evitar recálculos."""
    return hashlib.sha256(senha.encode("utf-8")).hexdigest()

def conectar_db():
    """
    Função de compatibilidade que usa o pool de conexões.
    Mantém compatibilidade com código existente.
    """
    try:
        conn = get_conn()
        print("✅ Conexão obtida do pool com sucesso!")
        return conn
    except Exception as e:
        print(f"❌ Erro ao obter conexão do pool: {e}")
        return None

def verificar_credenciais(
    usuario: str, 
    senha: str, 
    conexao=None
) -> Optional[Dict[str, str]]:
    """
    Verificação otimizada de credenciais.
    Usa pool de conexões se conexao não for fornecida.
    """
    usar_pool = conexao is None
    
    try:
        if usar_pool:
            conn = get_conn()
        else:
            conn = conexao
        
        cursor = conn.cursor()
        try:
            # Query otimizada - busca apenas campos necessários
            cursor.execute(
                "SELECT nome, cargo, senha FROM usuarios WHERE usuario = %s LIMIT 1", 
                (usuario,)
            )
            resultado = cursor.fetchone()
            
            if not resultado:
                return None
            
            nome, cargo, senha_db = resultado
            
            # Verifica senha direta primeiro (mais rápido)
            if senha == senha_db:
                return {"nome": nome, "cargo": cargo}
            
            # Verifica hash com cache
            senha_hash = _hash_senha(senha)
            if senha_hash == senha_db:
                return {"nome": nome, "cargo": cargo}
            
            return None
            
        finally:
            cursor.close()
            
    except psycopg2.Error as e:
        print(f"❌ Erro de banco ao verificar credenciais: {e}")
        return None
    except Exception as e:
        print(f"❌ Erro geral ao verificar credenciais: {e}")
        return None
    finally:
        if usar_pool and 'conn' in locals():
            put_conn(conn)

def verificar_usuario_existe(usuario: str) -> bool:
    """
    Verifica se usuário existe sem carregar dados desnecessários.
    """
    try:
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM usuarios WHERE usuario = %s LIMIT 1", 
                (usuario,)
            )
            exists = cursor.fetchone() is not None
            cursor.close()
            return exists
        finally:
            put_conn(conn)
    except Exception as e:
        print(f"❌ Erro ao verificar existência do usuário: {e}")
        return False

def obter_dados_usuario(usuario: str) -> Optional[Dict[str, Any]]:
    """
    Obtém dados completos de um usuário.
    """
    try:
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT usuario, nome, cargo FROM usuarios WHERE usuario = %s LIMIT 1",
                (usuario,)
            )
            resultado = cursor.fetchone()
            cursor.close()
            
            if resultado:
                return {
                    "usuario": resultado[0],
                    "nome": resultado[1], 
                    "cargo": resultado[2]
                }
            return None
            
        finally:
            put_conn(conn)
    except Exception as e:
        print(f"❌ Erro ao obter dados do usuário: {e}")
        return None

def testar_conexao() -> bool:
    """
    Testa se a conexão com banco está funcionando.
    """
    try:
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            return True
        finally:
            put_conn(conn)
    except Exception as e:
        print(f"❌ Teste de conexão falhou: {e}")
        return False

# Função de compatibilidade para código legado
def conectar_banco():
    """Alias para conectar_db() - compatibilidade."""
    return conectar_db()