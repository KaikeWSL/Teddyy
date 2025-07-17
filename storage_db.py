import datetime
import re
import unicodedata
import hashlib
import psycopg2
from functools import lru_cache
from contextlib import contextmanager
from typing import Dict, List, Optional, Any
from main.backend.db_connection import get_conn, put_conn

# --- Cache para normalização de nomes ---
@lru_cache(maxsize=128)
def _normalize(col_name: str) -> str:
    """Normaliza nomes de coluna com cache para melhor performance."""
    # Remove acentos
    s = unicodedata.normalize('NFKD', col_name)
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    # Minúsculas e '_' para não-alfanuméricos
    s = re.sub(r'[^0-9a-zA-Z]+', '_', s).lower().strip('_')
    # Casos especiais
    if s == 'n_serie':
        return 'serie'
    m = re.match(r'^data_pagamento_(\d+)$', s)
    if m:
        return f'data_pag{m.group(1)}'
    return s

@contextmanager
def get_db_cursor():
    """Context manager para gerenciar conexões de forma segura."""
    conn = get_conn()
    try:
        # Garante que a conexão está aberta
        if conn is None or (hasattr(conn, 'closed') and conn.closed):
            conn = get_conn()
        if conn is None or (hasattr(conn, 'closed') and conn.closed):
            raise Exception("Não foi possível obter uma conexão válida com o banco de dados.")
        # Limpa transação abortada se houver
        conn.rollback()
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
    finally:
        if conn is not None:
            put_conn(conn)

def get_table(table_name: str) -> List[Dict[str, Any]]:
    """Busca toda uma tabela sem normalizar nomes."""
    with get_db_cursor() as cur:
        cur.execute(f"SELECT * FROM {table_name}")
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    return [dict(zip(cols, row)) for row in rows]

def get_table_normalized(table_name: str) -> List[Dict[str, Any]]:
    """Busca com normalização de colunas e formatação de datas otimizada."""
    raw = get_table(table_name)
    
    # Pré-computa as normalizações das colunas uma vez
    if not raw:
        return []
    
    original_cols = list(raw[0].keys())
    normalized_cols = {col: _normalize(col) for col in original_cols}
    
    data = []
    for rec in raw:
        new = {}
        for original_col, value in rec.items():
            normalized_col = normalized_cols[original_col]
            # Formatação de datas otimizada
            if isinstance(value, (datetime.date, datetime.datetime)):
                new[normalized_col] = value.strftime("%d/%m/%Y")
            else:
                new[normalized_col] = value
        data.append(new)
    return data

# --- Carregamentos otimizados ---
def load_usuarios() -> Dict[str, Dict[str, str]]:
    """Carrega usuários com estrutura otimizada."""
    with get_db_cursor() as cur:
        cur.execute("SELECT usuario, senha, nome, cargo FROM usuarios")
        return {
            row[0]: {'senha': row[1], 'nome': row[2], 'cargo': row[3]}
            for row in cur.fetchall()
        }

def load_solicitacoes() -> List[Dict[str, Any]]:
    """Carrega solicitações."""
    return get_table_normalized('solicitacoes')

def load_clientes() -> List[Dict[str, Any]]:
    """Carrega clientes."""
    return get_table_normalized('clientes')

def load_equipamentos() -> List[Dict[str, Any]]:
    """Carrega equipamentos."""
    return get_table_normalized('equipamentos')

def get_os_cadastros() -> List[Dict[str, Any]]:
    """Carrega OS cadastros."""
    return get_table_normalized('os_cadastros')

def load_tecnicos() -> List[str]:
    """Carrega todos os nomes de técnicos cadastrados."""
    with get_db_cursor() as cur:
        cur.execute("SELECT nome FROM tecnicos ORDER BY nome")
        return [row[0] for row in cur.fetchall()]

def insert_tecnico(nome: str) -> None:
    """Insere um novo técnico se não existir."""
    with get_db_cursor() as cur:
        cur.execute("INSERT INTO tecnicos (nome) VALUES (%s) ON CONFLICT (nome) DO NOTHING", (nome,))

def load_gerentes() -> List[str]:
    """Carrega todos os nomes de gerentes cadastrados."""
    with get_db_cursor() as cur:
        cur.execute("SELECT nome FROM gerentes ORDER BY nome")
        return [row[0] for row in cur.fetchall()]

def insert_gerente(nome: str) -> None:
    """Insere um novo gerente se não existir."""
    with get_db_cursor() as cur:
        cur.execute("INSERT INTO gerentes (nome) VALUES (%s) ON CONFLICT (nome) DO NOTHING", (nome,))

# --- Operações de escrita otimizadas ---
def insert_solicitacao(usuario: str, senha_hash: str, nome: str) -> None:
    """Insere solicitação com transação segura."""
    with get_db_cursor() as cur:
        cur.execute(
            "INSERT INTO solicitacoes(usuario, senha_hash, nome) VALUES (%s, %s, %s)",
            (usuario, senha_hash, nome)
        )

def insert_os(
    id: Optional[int],
    os: str,
    cliente: str,
    modelo: str,
    entrada_equip: str,
    valor: str,
    saida_equip: str,
    pagamento: str,
    vezes: str,
    data_pag1: str,
    data_pag2: str,
    data_pag3: str,
    serie: str,
    tecnico: str,
    status: str,
    avaliacao_tecnica: Optional[str] = None,
    causa_provavel: Optional[str] = None,
) -> None:
    """Insere ou atualiza OS (upsert) usando id como chave única. Se id for None, gera novo automaticamente."""
    with get_db_cursor() as cur:
        if id is None:
            cur.execute('SELECT COALESCE(MAX(id), 0) + 1 FROM os_cadastros')
            id = cur.fetchone()[0]
        query = """
            INSERT INTO os_cadastros(
                id, "OS", "Cliente", "Modelo", "Entrada equip.", "Valor", 
                "Saída equip.", "Pagamento", "Vezes", "Data pagamento 1", 
                "Data pagamento 2", "Data pagamento 3", "N° Serie", 
                "Técnico", status, avaliacao_tecnica, causa_provavel
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (id) DO UPDATE SET
                "OS" = EXCLUDED."OS",
                "Cliente" = EXCLUDED."Cliente",
                "Modelo" = EXCLUDED."Modelo",
                "Entrada equip." = EXCLUDED."Entrada equip.",
                "Valor" = EXCLUDED."Valor",
                "Saída equip." = EXCLUDED."Saída equip.",
                "Pagamento" = EXCLUDED."Pagamento",
                "Vezes" = EXCLUDED."Vezes",
                "Data pagamento 1" = EXCLUDED."Data pagamento 1",
                "Data pagamento 2" = EXCLUDED."Data pagamento 2",
                "Data pagamento 3" = EXCLUDED."Data pagamento 3",
                "N° Serie" = EXCLUDED."N° Serie",
                "Técnico" = EXCLUDED."Técnico",
                status = EXCLUDED.status,
                avaliacao_tecnica = EXCLUDED.avaliacao_tecnica,
                causa_provavel = EXCLUDED.causa_provavel
        """
        params = (
            id, os, cliente, modelo, entrada_equip, valor, saida_equip, 
            pagamento, vezes, data_pag1, data_pag2, data_pag3,
            serie, tecnico, status, avaliacao_tecnica, causa_provavel
        )
        try:
            cur.execute(query, params)
            rows_affected = cur.rowcount
            print(f"Linhas afetadas: {rows_affected}")
            if rows_affected == 0:
                print("AVISO: Nenhuma linha foi inserida/atualizada")
            else:
                print(f"Sucesso: OS {os} salva no banco de dados")
        except Exception as e:
            print(f"ERRO ao salvar OS: {e}")
            raise

def delete_os(os_number: str) -> None:
    """Remove OS com transação segura."""
    with get_db_cursor() as cur:
        cur.execute('DELETE FROM os_cadastros WHERE "OS" = %s', (os_number,))

# --- Cache para hashes de senha ---
@lru_cache(maxsize=256)
def _hash_password(password: str) -> str:
    """Cache de hashes de senha para reduzir computação."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def authenticate_user(usuario: str, senha: str) -> Optional[Dict[str, str]]:
    """Autenticação otimizada com menos queries e cache."""
    
    try:
        with get_db_cursor() as cur:
            cur.execute(
                "SELECT senha, nome, cargo FROM usuarios WHERE usuario = %s",
                (usuario,)
            )
            row = cur.fetchone()
    except psycopg2.OperationalError:
        # Retry em caso de erro de conexão
        with get_db_cursor() as cur:
            cur.execute(
                "SELECT senha, nome, cargo FROM usuarios WHERE usuario = %s",
                (usuario,)
            )
            row = cur.fetchone()

    if row is None:
        return None

    db_senha, nome, cargo = row
    user_data = {"usuario": usuario, "nome": nome, "cargo": cargo}

    # Verifica senha direta primeiro (mais rápido)
    if senha == db_senha:
        return user_data

    # Depois verifica hash com cache
    senha_hash = _hash_password(senha)
    if senha_hash == db_senha:
        return user_data

    return None

# --- Operações administrativas otimizadas ---
def insert_usuario(usuario: str, senha_hash: str, nome: str, cargo: str) -> None:
    """Insere usuário com transação segura."""
    with get_db_cursor() as cur:
        cur.execute(
            "INSERT INTO usuarios (usuario, senha, nome, cargo) VALUES (%s, %s, %s, %s)",
            (usuario, senha_hash, nome, cargo)
        )

def update_usuario(usuario: str, campo: str, valor: str) -> None:
    """Atualiza usuário com validação de campo."""
    # Validação de segurança para campos permitidos
    campos_permitidos = {'senha', 'nome', 'cargo'}
    if campo not in campos_permitidos:
        raise ValueError(f"Campo '{campo}' não é permitido. Use: {campos_permitidos}")
    
    with get_db_cursor() as cur:
        # Usa f-string segura já que validamos o campo
        cur.execute(
            f'UPDATE usuarios SET "{campo}" = %s WHERE usuario = %s',
            (valor, usuario)
        )

def delete_solicitacao(usuario: str) -> None:
    """Remove solicitação com transação segura."""
    with get_db_cursor() as cur:
        cur.execute("DELETE FROM solicitacoes WHERE usuario = %s", (usuario,))

# --- Operações em lote para melhor performance ---
def insert_usuarios_bulk(usuarios_data: List[tuple]) -> None:
    """Insere múltiplos usuários em uma transação."""
    with get_db_cursor() as cur:
        cur.executemany(
            "INSERT INTO usuarios (usuario, senha, nome, cargo) VALUES (%s, %s, %s, %s)",
            usuarios_data
        )

def get_usuarios_by_cargo(cargo: str) -> List[Dict[str, Any]]:
    """Busca usuários por cargo com query específica."""
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT usuario, nome, cargo FROM usuarios WHERE cargo = %s",
            (cargo,)
        )
        return [
            {"usuario": row[0], "nome": row[1], "cargo": row[2]}
            for row in cur.fetchall()
        ]
    
def save_equipamentos(equipamentos: dict) -> None:
    """
    Salva todos os equipamentos no banco, atualizando apenas o que mudou.
    Espera um dict: {nome: [tipo, marca], ...}
    """
    with get_db_cursor() as cur:
        # Carrega todos os equipamentos atuais do banco
        cur.execute("SELECT equipamento, tipo, marca FROM equipamentos")
        existentes = {row[0]: (row[1], row[2]) for row in cur.fetchall()}

        # Descobre quais remover
        nomes_novos = set(equipamentos.keys())
        nomes_existentes = set(existentes.keys())
        a_remover = nomes_existentes - nomes_novos
        a_inserir = nomes_novos - nomes_existentes
        a_atualizar = {nome for nome in (nomes_novos & nomes_existentes)
                       if tuple(equipamentos[nome]) != existentes[nome]}

        # Remove os que não existem mais
        for nome in a_remover:
            cur.execute("DELETE FROM equipamentos WHERE equipamento = %s", (nome,))

        # Insere novos
        for nome in a_inserir:
            tipo, marca = equipamentos[nome]
            cur.execute(
                "INSERT INTO equipamentos (equipamento, tipo, marca) VALUES (%s, %s, %s)",
                (nome, tipo, marca)
            )

        # Atualiza alterados
        for nome in a_atualizar:
            tipo, marca = equipamentos[nome]
            cur.execute(
                "UPDATE equipamentos SET tipo = %s, marca = %s WHERE equipamento = %s",
                (tipo, marca, nome)
            )

# Adicione estas funções ao seu arquivo storage_db.py

def save_clientes(clientes: List[Dict[str, Any]]) -> None:
    """
    Salva todos os clientes no banco, substituindo os existentes.
    Espera uma lista de dicts com os dados dos clientes.
    """
    with get_db_cursor() as cur:
        # Remove todos os clientes antigos
        cur.execute("DELETE FROM clientes")
        
        # Insere todos os clientes novos
        for cliente in clientes:
            cur.execute(
                """INSERT INTO clientes (
                    nome, cpf_cnpj, endereco, bairro, numero, 
                    email, nome_contato, tel_contato
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    cliente.get('nome'),
                    cliente.get('cpf_cnpj'),
                    cliente.get('endereco'),
                    cliente.get('bairro'),
                    cliente.get('numero'),
                    cliente.get('email'),
                    cliente.get('nome_contato'),
                    cliente.get('tel_contato')
                )
            )

def insert_cliente(cliente: Dict[str, Any]) -> int:
    """
    Insere um novo cliente no banco de dados.
    Retorna o ID do cliente inserido.
    """
    with get_db_cursor() as cur:
        cur.execute(
            """INSERT INTO clientes (
                nome, cpf_cnpj, endereco, bairro, numero, 
                email, nome_contato, tel_contato
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id""",
            (
                cliente.get('nome'),
                cliente.get('cpf_cnpj'),
                cliente.get('endereco'),
                cliente.get('bairro'),
                cliente.get('numero'),
                cliente.get('email'),
                cliente.get('nome_contato'),
                cliente.get('tel_contato')
            )
        )
        return cur.fetchone()[0]

def update_cliente(cliente_id: int, cliente: Dict[str, Any]) -> None:
    """
    Atualiza um cliente existente no banco de dados.
    """
    if not cliente_id:
        raise ValueError("ID do cliente é obrigatório para atualização")
    
    with get_db_cursor() as cur:
        cur.execute(
            """UPDATE clientes SET 
                nome = %s, 
                cpf_cnpj = %s, 
                endereco = %s, 
                bairro = %s, 
                numero = %s,
                email = %s, 
                nome_contato = %s, 
                tel_contato = %s
            WHERE id = %s""",
            (
                cliente.get('nome'),
                cliente.get('cpf_cnpj'),
                cliente.get('endereco'),
                cliente.get('bairro'),
                cliente.get('numero'),
                cliente.get('email'),
                cliente.get('nome_contato'),
                cliente.get('tel_contato'),
                cliente_id
            )
        )

def delete_cliente(cliente_id: int) -> None:
    """
    Remove um cliente do banco de dados.
    """
    if not cliente_id:
        raise ValueError("ID do cliente é obrigatório para exclusão")
    
    with get_db_cursor() as cur:
        cur.execute("DELETE FROM clientes WHERE id = %s", (cliente_id,))

def get_cliente_by_id(cliente_id: int) -> Optional[Dict[str, Any]]:
    """
    Busca um cliente específico pelo ID.
    """
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM clientes WHERE id = %s", (cliente_id,))
        row = cur.fetchone()
        if row:
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
        return None

def get_cliente_by_nome(nome: str) -> List[Dict[str, Any]]:
    """
    Busca clientes pelo nome (busca parcial).
    """
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT * FROM clientes WHERE nome ILIKE %s ORDER BY nome",
            (f"%{nome}%",)
        )
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        return [dict(zip(cols, row)) for row in rows]

def get_cliente_by_cpf_cnpj(cpf_cnpj: str) -> Optional[Dict[str, Any]]:
    """
    Busca um cliente pelo CPF/CNPJ.
    """
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM clientes WHERE cpf_cnpj = %s", (cpf_cnpj,))
        row = cur.fetchone()
        if row:
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
        return None

def check_cliente_exists(nome: str, cpf_cnpj: str = None) -> bool:
    """
    Verifica se um cliente já existe no banco.
    """
    with get_db_cursor() as cur:
        if cpf_cnpj:
            cur.execute(
                "SELECT COUNT(*) FROM clientes WHERE nome = %s OR cpf_cnpj = %s",
                (nome, cpf_cnpj)
            )
        else:
            cur.execute(
                "SELECT COUNT(*) FROM clientes WHERE nome = %s",
                (nome,)
            )
        return cur.fetchone()[0] > 0
    




def init_clientes_table() -> None:
    """
    Inicializa a tabela de clientes se ela não existir.
    Chame esta função na inicialização da aplicação.
    """
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS clientes (
        id SERIAL PRIMARY KEY,
        nome VARCHAR(255) NOT NULL,
        cpf_cnpj VARCHAR(18),
        endereco TEXT,
        bairro VARCHAR(100),
        numero VARCHAR(20),
        email VARCHAR(255),
        nome_contato VARCHAR(255),
        tel_contato VARCHAR(20),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_clientes_nome ON clientes(nome);
    CREATE INDEX IF NOT EXISTS idx_clientes_cpf_cnpj ON clientes(cpf_cnpj);
    CREATE INDEX IF NOT EXISTS idx_clientes_email ON clientes(email);
    """
    
    # Função para atualizar updated_at
    update_function_sql = """
    CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ language 'plpgsql';
    """
    
    # Trigger para updated_at
    trigger_sql = """
    DROP TRIGGER IF EXISTS update_clientes_updated_at ON clientes;
    CREATE TRIGGER update_clientes_updated_at 
        BEFORE UPDATE ON clientes 
        FOR EACH ROW 
        EXECUTE FUNCTION update_updated_at_column();
    """
    
    try:
        with get_db_cursor() as cur:
            # Executa os comandos SQL
            cur.execute(create_table_sql)
            cur.execute(update_function_sql)
            cur.execute(trigger_sql)
            
        print("Tabela de clientes inicializada com sucesso!")
        
    except Exception as e:
        print(f"Erro ao inicializar tabela de clientes: {e}")
        raise

# Função para verificar se a tabela existe
def table_exists(table_name: str) -> bool:
    """
    Verifica se uma tabela existe no banco de dados.
    """
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = %s
            );""",
            (table_name,)
        )
        return cur.fetchone()[0]

# Função de migração/atualização da estrutura
def migrate_clientes_table() -> None:
    """
    Executa migrações necessárias na tabela de clientes.
    """
    try:
        with get_db_cursor() as cur:
            # Verifica se colunas existem e adiciona se necessário
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'clientes' 
                AND table_schema = 'public'
            """)
            
            existing_columns = {row[0] for row in cur.fetchall()}
            
            # Adiciona colunas que podem estar faltando
            required_columns = {
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
            }
            
            for col_name, col_definition in required_columns.items():
                if col_name not in existing_columns:
                    cur.execute(f'ALTER TABLE clientes ADD COLUMN {col_name} {col_definition}')
                    print(f"Coluna '{col_name}' adicionada à tabela clientes")
                    
    except Exception as e:
        print(f"Erro durante migração: {e}")
        raise    

def update_status_os(os_id: int, status: str) -> None:
    """Atualiza o status de uma OS pelo id."""
    with get_db_cursor() as cur:
        cur.execute("UPDATE os_cadastros SET status = %s WHERE id = %s", (status, os_id))  
        
          
def delete_tecnico(nome: str) -> None:
    """Remove um técnico pelo nome."""
    with get_db_cursor() as cur:
        cur.execute("DELETE FROM tecnicos WHERE nome = %s", (nome,))

def delete_gerente(nome: str) -> None:
    """Remove um gerente pelo nome."""
    with get_db_cursor() as cur:
        cur.execute("DELETE FROM gerentes WHERE nome = %s", (nome,))

def check_serial_autorizado(serial: str) -> bool:
    """Verifica se o serial da placa-mãe está autorizado na tabela 'autorizados'."""
    from main.backend.db_connection import get_conn, put_conn
    conn = None
    try:
        conn = get_conn()
        if not conn:
            return False
        cur = conn.cursor()
        cur.execute('SELECT 1 FROM autorizados WHERE serial_placa_mae = %s', (serial,))
        autorizado = cur.fetchone() is not None
        cur.close()
        return autorizado
    except Exception as e:
        print(f'Erro ao verificar autorização do serial: {e}')
        return False
    finally:
        if conn:
            put_conn(conn)