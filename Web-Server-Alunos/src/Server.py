import os
import logging
import argparse
import secrets
import json
import hashlib

from datetime import datetime, date
from functools import wraps
from getpass import getpass

from flask import (
    Flask, Blueprint, request, jsonify, session, redirect,
    make_response, url_for, render_template, g
)

from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity
)
from flasgger import Swagger, swag_from, LazyJSONEncoder
from sqlalchemy import create_engine, text, Column, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import IntegrityError

CONFIG_PATH = ""

app = Flask(__name__)

DB_USER = "Diogo"
DB_PASSWORD = "Alunos_dev"
## DB_PASSWORD = os.getenv("DB_PASSWORD", ""), depois faço a parte de colocar a password no .env, mas agora não tenho tempo para isso
DB_HOST = "mysql-db"
DB_PORT = 3306
DB_NAME = "Alunos"

DATABASE_URL = (
    f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "teste")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = 28800

CORS(app)
db = SQLAlchemy(app)
jwt = JWTManager(app)
bcrypt = Bcrypt(app)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

logging.basicConfig(level=logging.DEBUG)

## Swagger(app, template_file='../swagger/definitions.yaml'), proxima vez faço o swagger funcionar, mas agora não tenho tempo para isso


def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):

        aluno_id = get_jwt_identity()

        with engine.connect() as con:

            query = text("""
                SELECT is_admin, estado
                FROM Alunos
                WHERE aluno_id = :aluno_id
            """)

            aluno = con.execute(
                query,
                {'aluno_id': aluno_id}
            ).mappings().fetchone()

            if not aluno or aluno['estado'] != 'Ativo':
                return jsonify({
                    'message': 'Utilizador não encontrado ou inativo'
                }), 401

            if not aluno['is_admin']:
                return jsonify({
                    'message': 'Acesso negado. Apenas administradores.'
                }), 403

        return fn(*args, **kwargs)

    return wrapper

# ##############################################################################
# ----------------------------------- TURMAS -----------------------------------
# ##############################################################################

@app.route("/alunos", methods=["GET"])
def pagina_alunos():
    return render_template("alunosT.html")


@app.route("/api/alunos", methods=["GET"])
@jwt_required()
def get_alunos_api():

    with engine.connect() as con:
        query = text("""
            SELECT aluno_id, numero_aluno, nome_proprio, apelido, email
            FROM Alunos
            WHERE estado = 'Ativo'
            AND numero_aluno != '123'
        """)

        resultado = con.execute(query).mappings().all()

        alunos = [dict(aluno) for aluno in resultado]

        return jsonify({
            "alunos": alunos
        }), 200
    


@app.route("/adicionar_alunos", methods=["GET"])
def pagina_adicionar_aluno():
    return render_template("adicionar_alunosT.html")


@app.route("/api/alunos", methods=["POST"])
@admin_required
def adicionar_aluno_api():
    data = request.get_json(silent=True) or {}

    campos = ["numero_aluno", "nome_proprio", "apelido", "data_nascimento", "email", "telefone", "morada", "codigo_postal", "localidade", "passphrase"]

    if any(not data.get(campo) for campo in campos):
        return jsonify({"message": "Preencha todos os campos."}), 400

    data["passphrase"] = bcrypt.generate_password_hash(data["passphrase"]).decode("utf-8")

    query = text("""
        INSERT INTO Alunos (numero_aluno, nome_proprio, apelido, data_nascimento, email, telefone, morada, codigo_postal, localidade, passphrase)
        VALUES (:numero_aluno, :nome_proprio, :apelido, :data_nascimento, :email, :telefone, :morada, :codigo_postal, :localidade, :passphrase)
    """)

    try:
        with engine.begin() as con:
            resultado = con.execute(query, data)

        return jsonify({"message": "Aluno adicionado com sucesso.", "aluno_id": resultado.lastrowid}), 201

    except IntegrityError:
        return jsonify({"message": "Número de aluno ou email já existente."}), 409


@app.route("/remover_alunos", methods=["GET"])
def pagina_remover_alunos():
    return render_template("remover_alunosT.html")


@app.route("/api/alunos/estado", methods=["PUT"])
@admin_required
def alterar_estado_aluno():
    data = request.get_json(silent=True) or {}

    numero_aluno = data.get("numero_aluno")
    estado = data.get("estado")
    observacoes = data.get("observacoes") or None

    estados_validos = ["Inativo", "Transferido", "Concluido"]

    if not numero_aluno or estado not in estados_validos:
        return jsonify({"message": "Dados inválidos."}), 400

    with engine.begin() as con:
        aluno = con.execute(text("""
            SELECT aluno_id FROM Alunos
            WHERE numero_aluno = :numero_aluno
            AND numero_aluno != '123'
        """), {"numero_aluno": numero_aluno}).fetchone()

        if not aluno:
            return jsonify({"message": "Aluno não encontrado."}), 404

        con.execute(text("""
            UPDATE Alunos
            SET estado = :estado,
                observacoes = COALESCE(:observacoes, observacoes)
            WHERE numero_aluno = :numero_aluno
        """), {
            "estado": estado,
            "observacoes": observacoes,
            "numero_aluno": numero_aluno
        })

    return jsonify({"message": "Estado do aluno alterado com sucesso."}), 200

# ##############################################################################
# ----------------------------------- TURMAS -----------------------------------
# ##############################################################################

@app.route("/Turmas", methods=["GET"])
def pagina_turmas():
    return render_template("turmasT.html")


@app.route("/api/turmas", methods=["GET"])
@admin_required
def get_turmas_api():
    with engine.connect() as con:
        query = text("""
            SELECT turma_id, codigo, ano_letivo, limite_alunos, ativa
            FROM Turmas
            ORDER BY ano_letivo DESC, codigo ASC
        """)
        resultado = con.execute(query).mappings().all()
        turmas = [dict(turma) for turma in resultado]

    return jsonify({"turmas": turmas}), 200

@app.route("/adicionar_turmas", methods=["GET"])
def pagina_adicionar_turmas():
    return render_template("adicionar_turmasT.html")

@app.route("/api/turmas", methods=["POST"])
@admin_required
def adicionar_turma_api():
    data = request.get_json(silent=True) or {}

    codigo = data.get("codigo", "").strip() if isinstance(data.get("codigo"), str) else ""
    ano_letivo = data.get("ano_letivo", "")
    curso_id = data.get("curso_id") or None
    limite_alunos = data.get("limite_alunos", 30)
    ativa = data.get("ativa", True)

    if not codigo or len(codigo) > 20 or not isinstance(ano_letivo, str) or len(ano_letivo) != 9:
        return jsonify({"message": "Código ou ano letivo inválido."}), 400

    if not isinstance(limite_alunos, int) or isinstance(limite_alunos, bool) or not 1 <= limite_alunos <= 100 or not isinstance(ativa, bool):
        return jsonify({"message": "Limite de alunos ou estado inválido."}), 400

    query = text("""
        INSERT INTO Turmas (curso_id, codigo, ano_letivo, limite_alunos, ativa)
        VALUES (:curso_id, :codigo, :ano_letivo, :limite_alunos, :ativa)
    """)

    try:
        with engine.begin() as con:
            resultado = con.execute(query, {
                "curso_id": curso_id, "codigo": codigo,
                "ano_letivo": ano_letivo, "limite_alunos": limite_alunos,
                "ativa": ativa
            })

        return jsonify({"message": "Turma criada com sucesso.", "turma_id": resultado.lastrowid}), 201

    except IntegrityError:
        return jsonify({"message": "Turma já existente, opte por editá-la."}), 409



@app.route("/gerir_turmas", methods=["GET"])
def pagina_gerir_turmas():
    return render_template("gerir_turmasT.html")


@app.route("/api/turmas/<int:turma_id>", methods=["PUT"])
@admin_required
def editar_turma_api(turma_id):
    data = request.get_json(silent=True) or {}

    codigo = data.get("codigo")
    ano_letivo = data.get("ano_letivo")
    limite_alunos = data.get("limite_alunos")
    ativa = data.get("ativa")

    if not isinstance(codigo, str) or not codigo.strip() or len(codigo.strip()) > 20 or not isinstance(ano_letivo, str) or len(ano_letivo) != 9:
        return jsonify({"message": "Código ou ano letivo inválido."}), 400

    if not isinstance(limite_alunos, int) or isinstance(limite_alunos, bool) or not 1 <= limite_alunos <= 100 or not isinstance(ativa, bool):
        return jsonify({"message": "Limite de alunos ou estado inválido."}), 400

    try:
        with engine.begin() as con:
            turma = con.execute(text("""
                SELECT turma_id FROM Turmas
                WHERE turma_id = :turma_id
            """), {"turma_id": turma_id}).fetchone()

            if not turma:
                return jsonify({"message": "Turma não encontrada."}), 404

            con.execute(text("""
                UPDATE Turmas
                SET codigo = :codigo,
                    ano_letivo = :ano_letivo,
                    limite_alunos = :limite_alunos,
                    ativa = :ativa
                WHERE turma_id = :turma_id
            """), {
                "codigo": codigo.strip(),
                "ano_letivo": ano_letivo,
                "limite_alunos": limite_alunos,
                "ativa": ativa,
                "turma_id": turma_id
            })

        return jsonify({"message": "Turma atualizada com sucesso."}), 200

    except IntegrityError:
        return jsonify({"message": "Já existe uma turma com esse código e ano letivo."}), 409

# ##############################################################################
# ----------------------------------- LOGIN -----------------------------------
# ##############################################################################


@app.route('/login-page', methods=['GET'])
def login_page():
    return render_template('loginT.html')


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or request.form

    numero_aluno = data.get('numero_aluno')
    passphrase = data.get('passphrase')

    if not numero_aluno or not passphrase:
        return jsonify({'message': 'Preencha todos os campos'}), 400

    with engine.connect() as con:
        query = text("""
            SELECT aluno_id, numero_aluno, passphrase, is_admin, estado
            FROM Alunos
            WHERE numero_aluno = :numero_aluno
        """)

        aluno = con.execute(query, {'numero_aluno': numero_aluno}).mappings().fetchone()

        if not aluno or aluno['estado'] != 'Ativo':
            return jsonify({'message': 'Credenciais inválidas'}), 401

        if not bcrypt.check_password_hash(aluno['passphrase'], passphrase):
            return jsonify({'message': 'Credenciais inválidas'}), 401

        access_token = create_access_token(identity=str(aluno['aluno_id']))

        return jsonify({
            'access_token': access_token,
            'aluno_id': aluno['aluno_id'],
            'numero_aluno': aluno['numero_aluno'],
            'is_admin': bool(aluno['is_admin'])
        }), 200

@app.route("/api/admin", methods=["GET"])
@admin_required
def verificar_admin():
    return jsonify({"message": "Acesso autorizado"}), 200

@app.route("/admin", methods=["GET"])
def pagina_admin():
    return render_template("adminT.html")

@app.route('/')
def root():
    return render_template('indexT.html')