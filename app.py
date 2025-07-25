from flask import Flask, request, jsonify, session, send_from_directory, g
import psycopg2
from psycopg2 import pool
import hashlib
from datetime import datetime, timedelta
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
from flask_cors import CORS
import os
import pandas as pd
import unicodedata
import jwt
from functools import wraps
import threading
import time
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'  # Troque por uma chave forte
CORS(app, supports_credentials=True)
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True

# Controle de tentativas de login
login_attempts = {}
LOCKOUT_TIME = 300  # segundos
MAX_ATTEMPTS = 3

SECRET_KEY = 'sua_chave_secreta_super_segura'  # Troque por uma chave forte e secreta
JWT_EXP_DELTA_SECONDS = 3600  # 1 hora

# Configuração do pool de conexões
connection_pool = None
pool_lock = threading.Lock()

def create_connection_pool():
    """Cria o pool de conexões com configurações otimizadas"""
    global connection_pool
    try:
        connection_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,  # Mínimo de conexões
            maxconn=20,  # Máximo de conexões
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            # Configurações para manter conexão viva
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=5,
            # Timeout de conexão
            connect_timeout=10
        )
        logger.info("Pool de conexões criado com sucesso")
        return True
    except Exception as e:
        logger.error(f"Erro ao criar pool de conexões: {str(e)}")
        return False

def get_db_conn():
    """Obtém uma conexão do pool com retry automático"""
    global connection_pool
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            with pool_lock:
                if connection_pool is None:
                    logger.info("Recriando pool de conexões...")
                    if not create_connection_pool():
                        raise Exception("Falha ao criar pool de conexões")
                
                conn = connection_pool.getconn()
                
                # Testa a conexão
                if conn.closed != 0:
                    logger.warning("Conexão fechada detectada, obtendo nova conexão...")
                    connection_pool.putconn(conn, close=True)
                    conn = connection_pool.getconn()
                
                # Teste simples para verificar se a conexão está ativa
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
                
                return conn
                
        except Exception as e:
            logger.error(f"Erro ao obter conexão (tentativa {retry_count + 1}): {str(e)}")
            retry_count += 1
            
            if retry_count < max_retries:
                # Tenta recriar o pool
                with pool_lock:
                    if connection_pool:
                        try:
                            connection_pool.closeall()
                        except:
                            pass
                        connection_pool = None
                
                time.sleep(1)  # Aguarda 1 segundo antes de tentar novamente
            else:
                raise Exception(f"Falha ao obter conexão após {max_retries} tentativas")

def return_db_conn(conn):
    """Retorna uma conexão para o pool"""
    global connection_pool
    if connection_pool and conn:
        try:
            connection_pool.putconn(conn)
        except Exception as e:
            logger.error(f"Erro ao retornar conexão: {str(e)}")

def close_db_conn(conn):
    """Fecha uma conexão defeituosa"""
    global connection_pool
    if connection_pool and conn:
        try:
            connection_pool.putconn(conn, close=True)
        except Exception as e:
            logger.error(f"Erro ao fechar conexão: {str(e)}")

def health_check():
    """Verifica a saúde do pool de conexões periodicamente"""
    while True:
        try:
            time.sleep(300)  # Verifica a cada 5 minutos
            
            with pool_lock:
                if connection_pool:
                    # Testa uma conexão do pool
                    conn = None
                    try:
                        conn = connection_pool.getconn()
                        with conn.cursor() as cur:
                            cur.execute("SELECT version()")
                            cur.fetchone()
                        connection_pool.putconn(conn)
                        logger.info("Health check: Pool de conexões OK")
                    except Exception as e:
                        logger.error(f"Health check falhou: {str(e)}")
                        if conn:
                            connection_pool.putconn(conn, close=True)
                        
        except Exception as e:
            logger.error(f"Erro no health check: {str(e)}")

# Inicia o thread de monitoramento
health_thread = threading.Thread(target=health_check, daemon=True)
health_thread.start()

def hash_password(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

# Função para gerar token JWT
def gerar_token(usuario, nome, cargo):
    payload = {
        'usuario': usuario,
        'nome': nome,
        'cargo': cargo,
        'exp': datetime.utcnow() + timedelta(seconds=JWT_EXP_DELTA_SECONDS)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

# Função para validar token JWT
def validar_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def login_required_jwt(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'erro': 'Token não fornecido'}), 401
        token = auth_header.split(' ')[1]
        payload = validar_token(token)
        if not payload:
            return jsonify({'erro': 'Token inválido ou expirado'}), 401
        g.usuario_jwt = payload  # Disponível na view
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    if not data:
        return jsonify({'erro': 'Dados inválidos'}), 400
    usuario = data.get('usuario')
    senha = data.get('senha')
    ip = request.remote_addr
    now = datetime.now()
    key = f'{usuario}_{ip}'

    # Bloqueio por tentativas
    if key in login_attempts:
        attempts, last_time = login_attempts[key]
        if attempts >= MAX_ATTEMPTS and (now - last_time).total_seconds() < LOCKOUT_TIME:
            return jsonify({'erro': f'Conta bloqueada. Tente novamente em {LOCKOUT_TIME - int((now - last_time).total_seconds())} segundos.'}), 403
        elif (now - last_time).total_seconds() >= LOCKOUT_TIME:
            login_attempts[key] = (0, now)

    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute('SELECT usuario, senha, nome, cargo FROM usuarios WHERE usuario = %s', (usuario,))
        row = cur.fetchone()
        cur.close()
        
        if row:
            senha_hash = row[1]
            if senha_hash == senha or senha_hash == hash_password(senha):
                login_attempts[key] = (0, now)
                token = gerar_token(usuario, row[2], row[3])
                if isinstance(token, bytes):
                    token = token.decode('utf-8')
                return jsonify({'mensagem': 'Login realizado', 'token': token, 'nome': row[2], 'cargo': row[3]})
        
        # Falha
        if key in login_attempts:
            login_attempts[key] = (login_attempts[key][0]+1, now)
        else:
            login_attempts[key] = (1, now)
        return jsonify({'erro': 'Usuário ou senha inválidos.'}), 401
    except Exception as e:
        if conn:
            close_db_conn(conn)
        return jsonify({'erro': f'Erro no login: {str(e)}'}), 500
    finally:
        if conn:
            return_db_conn(conn)

@app.route('/api/resumo_os', methods=['GET'])
@login_required_jwt
def resumo_os():
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute('SELECT "Cliente", "Modelo", "OS", "Entrada", "Valor", "Saída", "Técnico", id FROM os_cadastros ORDER BY id DESC LIMIT 20')
        rows = cur.fetchall()
        cur.close()
        
        resultado = [
            {
                'Cliente': r[0],
                'Modelo': r[1],
                'OS': r[2],
                'Entrada': r[3],
                'Valor': r[4],
                'Saida': r[5],
                'Tecnico': r[6],
                'id': r[7]
            } for r in rows
        ]
        return jsonify(resultado)
    except Exception as e:
        if conn:
            close_db_conn(conn)
        return jsonify({'erro': f'Erro ao buscar OS: {str(e)}'}), 500
    finally:
        if conn:
            return_db_conn(conn)

@app.route('/api/abrir_os', methods=['POST'])
@login_required_jwt
def abrir_os():
    data = request.json
    if not data:
        return jsonify({'erro': 'Dados inválidos'}), 400
    cliente = data.get('Cliente')
    modelo = data.get('Modelo')
    os_num = data.get('OS')
    entrada = data.get('Entrada')
    valor = data.get('Valor')
    saida = data.get('Saida')
    tecnico = data.get('Tecnico')
    
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute('INSERT INTO os_cadastros ("Cliente", "Modelo", "OS", "Entrada", "Valor", "Saída", "Técnico") VALUES (%s, %s, %s, %s, %s, %s, %s)',
                    (cliente, modelo, os_num, entrada, valor, saida, tecnico))
        conn.commit()
        cur.close()
        return jsonify({'mensagem': 'OS aberta com sucesso!'})
    except Exception as e:
        if conn:
            conn.rollback()
            close_db_conn(conn)
        return jsonify({'erro': f'Erro ao abrir OS: {str(e)}'}), 500
    finally:
        if conn:
            return_db_conn(conn)

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'mensagem': 'Logout realizado'})

@app.route('/api/os_todos', methods=['GET'])
@login_required_jwt
def os_todos():
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute('SELECT * FROM os_cadastros ORDER BY id DESC')
        colnames = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        cur.close()
        logger.info(f"Colunas encontradas: {colnames}")
        logger.info(f"Número de registros: {len(rows)}")
        resultado = [dict(zip(colnames, r)) for r in rows]
        return jsonify(resultado)
    except Exception as e:
        logger.error(f"Erro em os_todos: {str(e)}")
        if conn:
            close_db_conn(conn)
        return jsonify({'erro': f'Erro ao buscar OS: {str(e)}'}), 500
    finally:
        if conn:
            return_db_conn(conn)

@app.route('/api/os_detalhe/<int:os_id>', methods=['GET'])
@login_required_jwt
def os_detalhe(os_id):
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute('SELECT * FROM os_cadastros WHERE id = %s', (os_id,))
        colnames = [desc[0] for desc in cur.description]
        row = cur.fetchone()
        cur.close()
        
        if row:
            return jsonify(dict(zip(colnames, row)))
        else:
            return jsonify({'erro': 'OS não encontrada'}), 404
    except Exception as e:
        if conn:
            close_db_conn(conn)
        return jsonify({'erro': f'Erro ao buscar detalhes da OS: {str(e)}'}), 500
    finally:
        if conn:
            return_db_conn(conn)

@app.route('/api/os_arquivos/<cliente>/<os_num>', methods=['GET'])
@login_required_jwt
def os_arquivos(cliente, os_num):
    def normalizar(s):
        return unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII').replace(' ', '').lower()
    base_dir = 'C:/OS'
    # Busca tolerante para cliente
    cliente_dirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))] if os.path.isdir(base_dir) else []
    cliente_norm = normalizar(cliente)
    cliente_match = next((d for d in cliente_dirs or [] if normalizar(d) == cliente_norm), None)
    if not cliente_match:
        return jsonify({'arquivos': []})
    cliente_path = os.path.join(base_dir, cliente_match)
    # Busca tolerante para OS
    os_dirs = [d for d in os.listdir(cliente_path) if os.path.isdir(os.path.join(cliente_path, d))] if os.path.isdir(cliente_path) else []
    os_norm = normalizar(os_num)
    os_match = next((d for d in os_dirs or [] if normalizar(d) == os_norm), None)
    if not os_match:
        return jsonify({'arquivos': []})
    base_path = os.path.join(cliente_path, os_match)
    arquivos = []
    if os.path.isdir(base_path):
        for nome in os.listdir(base_path):
            if nome.lower().endswith(('.pdf')):
                arquivos.append(nome)
    return jsonify({'arquivos': arquivos})

@app.route('/api/download_arquivo/<cliente>/<os_num>/<nome_arquivo>', methods=['GET'])
@login_required_jwt
def download_arquivo(cliente, os_num, nome_arquivo):
    base_path = os.path.join('C:/OS', cliente, os_num)
    if not os.path.isdir(base_path):
        return jsonify({'erro': 'Arquivo não encontrado'}), 404
    try:
        return send_from_directory(base_path, nome_arquivo, as_attachment=True)
    except Exception as e:
        return jsonify({'erro': f'Erro ao baixar arquivo: {str(e)}'}), 500

@app.route('/api/grafico_mensal/<int:ano>', methods=['GET'])
@login_required_jwt
def grafico_mensal(ano):
    conn = None
    try:
        conn = get_db_conn()
        df = pd.read_sql('SELECT "Saída equip.", "Valor" FROM os_cadastros', conn)
        
        df = df.dropna(subset=["Saída equip.", "Valor"])  # Remove linhas sem data ou valor
        df['saida'] = pd.to_datetime(df['Saída equip.'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['saida'])
        if df.empty:
            meses = [str(m).zfill(2) for m in range(1, 13)]
            valores = [0.0 for _ in range(1, 13)]
            return jsonify({'meses': meses, 'valores': valores})
        df['Valor'] = df['Valor'].fillna('0')
        df['valor_num'] = pd.to_numeric(df['Valor'].astype(str).str.replace('R$', '').str.replace('.', '').str.replace(',', '.'), errors='coerce')
        df['valor_num'] = df['valor_num'].fillna(0)
        # Garante que 'saida' é datetime antes de usar .dt
        if 'saida' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['saida']):
            df['saida'] = pd.to_datetime(df['saida'], errors='coerce')
        if 'saida' in df.columns and pd.api.types.is_datetime64_any_dtype(df['saida']):
            df_year = df[df['saida'].dt.year == ano]
            mensal = df_year.groupby(df_year['saida'].dt.month)['valor_num'].sum().to_dict()
        else:
            mensal = {}
        meses = [str(m).zfill(2) for m in range(1, 13)]
        valores = [mensal.get(m, 0.0) for m in range(1, 13)]
        return jsonify({'meses': meses, 'valores': valores})
    except Exception as e:
        if conn:
            close_db_conn(conn)
        return jsonify({'erro': f'Erro ao gerar gráfico: {str(e)}'}), 500
    finally:
        if conn:
            return_db_conn(conn)

@app.route('/api/grafico_comparativo/<int:ano1>/<int:ano2>', methods=['GET'])
@login_required_jwt
def grafico_comparativo(ano1, ano2):
    conn = None
    try:
        conn = get_db_conn()
        df = pd.read_sql('SELECT "Saída equip.", "Valor" FROM os_cadastros', conn)
        
        df = df.dropna(subset=["Saída equip.", "Valor"])  # Remove linhas sem data ou valor
        df['saida'] = pd.to_datetime(df['Saída equip.'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['saida'])
        if df.empty:
            meses = [str(m).zfill(2) for m in range(1, 13)]
            valores1 = [0.0 for _ in range(1, 13)]
            valores2 = [0.0 for _ in range(1, 13)]
            return jsonify({'meses': meses, 'valores1': valores1, 'valores2': valores2})
        df['Valor'] = df['Valor'].fillna('0')
        df['valor_num'] = pd.to_numeric(df['Valor'].astype(str).str.replace('R$', '').str.replace('.', '').str.replace(',', '.'), errors='coerce')
        df['valor_num'] = df['valor_num'].fillna(0)
        # Garante que 'saida' é datetime antes de usar .dt
        if 'saida' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['saida']):
            df['saida'] = pd.to_datetime(df['saida'], errors='coerce')
        if 'saida' in df.columns and pd.api.types.is_datetime64_any_dtype(df['saida']):
            df1 = df[df['saida'].dt.year == ano1]
            df2 = df[df['saida'].dt.year == ano2]
            mensal1 = df1.groupby(df1['saida'].dt.month)['valor_num'].sum().to_dict()
            mensal2 = df2.groupby(df2['saida'].dt.month)['valor_num'].sum().to_dict()
        else:
            mensal1 = {}
            mensal2 = {}
        meses = [str(m).zfill(2) for m in range(1, 13)]
        valores1 = [mensal1.get(m, 0.0) for m in range(1, 13)]
        valores2 = [mensal2.get(m, 0.0) for m in range(1, 13)]
        return jsonify({'meses': meses, 'valores1': valores1, 'valores2': valores2})
    except Exception as e:
        if conn:
            close_db_conn(conn)
        return jsonify({'erro': f'Erro ao gerar gráfico comparativo: {str(e)}'}), 500
    finally:
        if conn:
            return_db_conn(conn)

@app.route('/api/health', methods=['GET'])
def health():
    """Endpoint para verificar a saúde da aplicação e do banco"""
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute('SELECT 1')
        cur.fetchone()
        cur.close()
        return_db_conn(conn)
        return jsonify({'status': 'OK', 'database': 'connected'})
    except Exception as e:
        return jsonify({'status': 'ERROR', 'database': 'disconnected', 'error': str(e)}), 500

# Cleanup do pool quando a aplicação é finalizada
@app.teardown_appcontext
def cleanup(error):
    pass

def cleanup_pool():
    global connection_pool
    if connection_pool:
        connection_pool.closeall()

import atexit
atexit.register(cleanup_pool)

if __name__ == '__main__':
    # Inicializa o pool de conexões
    if not create_connection_pool():
        logger.error("Falha ao inicializar o pool de conexões")
        exit(1)
    
    app.run(host='0.0.0.0', port=5000)