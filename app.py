import argparse
import json
import os
import re
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from functools import wraps

import bcrypt
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, render_template_string, request, session, url_for

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "troque-esta-chave")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
)

DEFAULT_TANKS = [
    {
        "campo_id": "campo_ba_01",
        "campo_nome": "Campo Bahia Norte",
        "tanque_id": "tnk_001",
        "tanque_nome": "Tanque 001",
        "sheet_tab": "Tanque 001",
        "sheet_key": "TNK001",
    },
    {
        "campo_id": "campo_ba_01",
        "campo_nome": "Campo Bahia Norte",
        "tanque_id": "tnk_002",
        "tanque_nome": "Tanque 002",
        "sheet_tab": "Tanque 002",
        "sheet_key": "TNK002",
    },
    {
        "campo_id": "campo_ba_02",
        "campo_nome": "Campo Bahia Sul",
        "tanque_id": "tnk_003",
        "tanque_nome": "Tanque 003",
        "sheet_tab": "Tanque 003",
        "sheet_key": "TNK003",
    },
]

SITUACAO_OPTIONS = [
    "Prod",
    "Disp",
    "Rece",
    "Rece tk1",
    "Rece tk2",
    "Rece tk5",
    "Rece tk6",
    "Rece cx API",
    "Rece carreta",
    "Forn",
    "Forn tk2",
    "Forn tk4",
    "Forn tk5",
    "Forn tk6",
    "Dren",
    "Dren car",
    "Dren carr",
    "Dren ct1",
    "Dren cx API",
    "Dren tk8",
    "Inj",
    "Vend",
]
OIL_HELP_TOPICS = [
    {
        "id": "manual",
        "keywords": ["manual", "formulario", "registrar", "manobra", "medicao", "campo", "tanque"],
        "answer": (
            "Para registrar manualmente: selecione Campo e Tanque, informe Data, Hora (de 15 em 15 minutos), "
            "Medida e Situacao, depois clique em 'Salvar Medicao'."
        ),
    },
    {
        "id": "oil_format",
        "keywords": ["oil", "formato", "mensagem", "tp", "inj", "sintaxe"],
        "answer": (
            "Formato OIL: <tanque_ref> <medida> <HH:MM> <situacao> [observacao]. "
            "Exemplo: tp-400-03 230 14:20 inj."
        ),
    },
    {
        "id": "situacao",
        "keywords": ["situacao", "inj", "prod", "disp", "vend", "rece", "forn", "dren"],
        "answer": (
            "Situacoes aceitas incluem: Prod, Disp, Rece, Forn, Dren, Inj, Vend e variacoes configuradas no sistema."
        ),
    },
    {
        "id": "historico",
        "keywords": ["historico", "excluir", "apagar", "registro", "dia"],
        "answer": (
            "No Historico do Dia voce pode revisar as manobras e excluir um registro usando o botao 'Excluir'."
        ),
    },
    {
        "id": "whatsapp",
        "keywords": ["whatsapp", "grupo", "webhook", "envio"],
        "answer": (
            "O envio para WhatsApp depende de WHATSAPP_GROUP_WEBHOOK_URL configurado no .env. "
            "Se o webhook estiver vazio, a medicao salva normalmente sem envio ao grupo."
        ),
    },
]
HISTORY_DB_PATH = os.getenv("HISTORY_DB_PATH", os.path.join(BASE_DIR, "syspetro.db"))

LOGIN_TEMPLATE = """
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>SysPetrosynergy - Login</title>
  <style>
    :root { --bg:#0f172a; --panel:#111827; --line:#334155; --text:#e5e7eb; --accent:#1d4ed8; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; font-family:Segoe UI, sans-serif; color:var(--text);
      background: radial-gradient(circle at 10% 10%, rgba(180,83,9,.25), transparent 35%), linear-gradient(140deg, #020617, var(--bg));
      display:grid; place-items:center; padding:16px; }
    .card { width:100%; max-width:420px; background:rgba(17,24,39,.9); border:1px solid var(--line); border-radius:16px; padding:24px; }
    h1 { margin:0 0 6px; font-size:30px; }
    p { margin:0 0 14px; color:#cbd5e1; }
    input { width:100%; border:1px solid var(--line); border-radius:10px; background:#0b1220; color:white; padding:12px; margin-top:10px; }
    button, .btn { width:100%; border:none; border-radius:10px; background:var(--accent); color:white; font-weight:700; padding:12px; margin-top:14px; cursor:pointer; text-decoration:none; display:block; text-align:center; }
    .btn.sec { background:transparent; border:1px solid var(--line); }
    .err { margin-top:10px; color:#fca5a5; font-size:14px; }
  </style>
</head>
<body>
  <main class="card">
    <h1>SysPetrosynergy</h1>
    <p>Acesso do operador de campo</p>
    <form method="post" action="{{ url_for('login') }}">
      <input name="login" placeholder="Email ou matricula" required />
      <input name="senha" type="password" placeholder="Senha" required />
      <button type="submit">Entrar</button>
    </form>
    <a class="btn sec" href="{{ url_for('register') }}">Registrar</a>
    {% if error %}<div class="err">{{ error }}</div>{% endif %}
  </main>
</body>
</html>
"""

REGISTER_TEMPLATE = """
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>SysPetro - Registrar</title>
  <style>
    :root { --bg:#0f172a; --panel:#111827; --line:#334155; --text:#e5e7eb; --accent:#1d4ed8; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; font-family:Segoe UI, sans-serif; color:var(--text);
      background: radial-gradient(circle at 10% 10%, rgba(180,83,9,.25), transparent 35%), linear-gradient(140deg, #020617, var(--bg));
      display:grid; place-items:center; padding:16px; }
    .card { width:100%; max-width:460px; background:rgba(17,24,39,.9); border:1px solid var(--line); border-radius:16px; padding:24px; }
    h1 { margin:0 0 6px; font-size:30px; }
    p { margin:0 0 14px; color:#cbd5e1; }
    input { width:100%; border:1px solid var(--line); border-radius:10px; background:#0b1220; color:white; padding:12px; margin-top:10px; }
    button, .btn { width:100%; border:none; border-radius:10px; background:var(--accent); color:white; font-weight:700; padding:12px; margin-top:14px; cursor:pointer; text-decoration:none; display:block; text-align:center; }
    .btn.sec { background:transparent; border:1px solid var(--line); }
    .err { margin-top:10px; color:#fca5a5; font-size:14px; }
    .ok { margin-top:10px; color:#86efac; font-size:14px; }
  </style>
</head>
<body>
  <main class="card">
    <h1>Registrar Operador</h1>
    <p>Crie um novo acesso para o sistema</p>
    <form method="post" action="{{ url_for('register') }}">
      <input name="name" placeholder="Nome completo" required />
      <input name="login" placeholder="Email ou matricula" required />
      <input name="senha" type="password" placeholder="Senha" required />
      <input name="confirmar_senha" type="password" placeholder="Confirmar senha" required />
      <button type="submit">Criar conta</button>
    </form>
    <a class="btn sec" href="{{ url_for('login') }}">Voltar ao login</a>
    {% if error %}<div class="err">{{ error }}</div>{% endif %}
    {% if success %}<div class="ok">{{ success }}</div>{% endif %}
  </main>
</body>
</html>
"""

APP_TEMPLATE = """
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&icon_names=oil_barrel" />
  <title>SysPetrosynergy</title>
  <style>
    :root { --bg:#0f172a; --panel:#111827; --line:#334155; --text:#e5e7eb; --accent:#1d4ed8; --ok:#10b981; --err:#ef4444; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; font-family:Segoe UI, sans-serif; color:var(--text);
      background: radial-gradient(circle at 15% 10%, rgba(180,83,9,.2), transparent 35%), linear-gradient(135deg, #020617, var(--bg));
      padding:16px; }
    .wrap { max-width:780px; margin:0 auto; }
    .bar { display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; gap:10px; flex-wrap:wrap; }
    .brand { font-size:26px; margin:0; }
    .sub { margin:2px 0 0; color:#cbd5e1; font-size:14px; }
    .logout { border:1px solid var(--line); background:transparent; color:white; border-radius:10px; padding:8px 12px; text-decoration:none; }
    .top-actions { display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; }
    .hist-link { border:1px solid var(--line); background:transparent; color:white; border-radius:10px; padding:8px 12px; text-decoration:none; display:inline-flex; align-items:center; gap:8px; }
    .calc-link { border-color:#1d4ed8; color:#bfdbfe; }
    .calc-link:hover { background:rgba(29,78,216,.15); }
    .menu-toggle { display:none; width:auto; border:1px solid var(--line); background:#0b1220; color:#e5e7eb; border-radius:10px; padding:8px 12px; font-weight:700; }
    .mobile-menu-backdrop { display:none; position:fixed; inset:0; background:rgba(2,6,23,.58); z-index:39; }
    .mobile-menu { display:none; position:fixed; top:0; right:0; width:min(320px, 90vw); height:100vh; background:#0b1220; border-left:1px solid var(--line); z-index:40; padding:16px; }
    .mobile-menu.open, .mobile-menu-backdrop.open { display:block; }
    .mobile-menu-head { display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; }
    .mobile-close { width:auto; border:1px solid var(--line); background:#111827; color:#e5e7eb; border-radius:8px; padding:6px 10px; font-weight:600; }
    .mobile-actions { display:grid; gap:8px; }
    .mobile-actions .hist-link, .mobile-actions .logout { width:100%; justify-content:center; text-align:center; }
    .folder-mini { width:14px; height:10px; display:inline-block; border:1px solid #94a3b8; border-radius:2px; position:relative; background:#1e293b; }
    .folder-mini::before { content:""; position:absolute; top:-4px; left:1px; width:7px; height:4px; border:1px solid #94a3b8; border-bottom:none; border-radius:2px 2px 0 0; background:#334155; }
    .calc-mini { width:14px; height:14px; display:inline-grid; place-items:center; border:1px solid #93c5fd; border-radius:3px; font-size:10px; line-height:1; color:#bfdbfe; }
    .card { background:rgba(17,24,39,.9); border:1px solid var(--line); border-radius:16px; padding:18px; }
    .calc-results { margin-top:10px; border:1px solid #1f3a5c; border-radius:10px; padding:10px; background:rgba(11,18,32,.6); display:grid; gap:6px; }
    .calc-line { font-size:14px; color:#cbd5e1; }
    .calc-line strong { color:#bfdbfe; }
    .grid { display:grid; gap:10px; }
    label { font-size:14px; color:#cbd5e1; }
    input, select, textarea { width:100%; border:1px solid var(--line); border-radius:10px; background:#0b1220; color:white; padding:12px; }
    textarea { min-height:90px; resize:vertical; }
    button { width:100%; border:none; border-radius:10px; background:var(--accent); color:white; font-weight:700; padding:13px; cursor:pointer; }
    .msg { margin-top:12px; font-size:14px; }
    .ok { color:#86efac; }
    .error { color:#fca5a5; }
    .table-wrap { overflow:auto; border:1px solid var(--line); border-radius:12px; }
    table { width:100%; border-collapse:collapse; min-width:980px; }
    th, td { padding:9px 10px; border-bottom:1px solid #233047; text-align:left; font-size:13px; }
    th { color:#93c5fd; background:#0b1220; position:sticky; top:0; }
    .status-ok { color:#86efac; font-weight:700; }
    .status-erro { color:#fca5a5; font-weight:700; }
    .historico-groups { display:grid; gap:10px; }
    .hist-folder { border:1px solid var(--line); border-radius:12px; overflow:hidden; background:rgba(11,18,32,.65); }
    .hist-folder > summary { list-style:none; cursor:pointer; padding:10px 12px; border-bottom:1px solid #233047; display:flex; align-items:center; gap:8px; font-weight:700; color:#cbd5e1; }
    .hist-folder > summary::-webkit-details-marker { display:none; }
    .folder-icon { width:16px; height:12px; display:inline-block; border:1px solid #94a3b8; border-radius:2px; position:relative; background:#1e293b; }
    .folder-icon::before { content:""; position:absolute; top:-4px; left:1px; width:8px; height:4px; border:1px solid #94a3b8; border-bottom:none; border-radius:2px 2px 0 0; background:#334155; }
    .group-table-wrap { overflow:auto; }
    .group-table { min-width:1100px; }
    .btn-del { border:1px solid #7f1d1d; background:#3f1010; color:#fecaca; border-radius:8px; padding:6px 8px; font-size:12px; cursor:pointer; }
    .btn-del:hover { background:#5b1111; }
    .oil-fab { position:fixed; right:20px; bottom:20px; width:74px; height:74px; border-radius:999px; border:2px solid #60a5fa;
      background:radial-gradient(circle at 30% 30%, #2563eb, #0b1220 65%); box-shadow:0 10px 28px rgba(0,0,0,.5); cursor:pointer; z-index:30;
      display:grid; place-items:center; color:#bfdbfe; }
    .oil-fab:hover { transform:translateY(-2px); }
    .oil-icon { font-family:"Material Symbols Outlined"; font-variation-settings:"FILL" 1, "wght" 600, "GRAD" 0, "opsz" 48; font-size:40px; line-height:1; }
    .oil-tip { position:fixed; right:20px; bottom:102px; max-width:270px; background:rgba(17,24,39,.96); border:1px solid #374151;
      border-radius:12px; color:#e5e7eb; padding:9px 11px; font-size:12px; box-shadow:0 8px 18px rgba(0,0,0,.35); z-index:29; }
    .oil-tip::after { content:""; position:absolute; right:22px; bottom:-8px; width:12px; height:12px; background:rgba(17,24,39,.96);
      border-right:1px solid #374151; border-bottom:1px solid #374151; transform:rotate(45deg); }
    .oil-panel { position:fixed; right:20px; bottom:106px; width:min(420px, calc(100vw - 32px)); background:rgba(17,24,39,.97); border:1px solid #374151; border-radius:14px; padding:14px; z-index:31; display:none; }
    .oil-panel.open { display:block; }
    .oil-top { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:8px; }
    .oil-close { width:auto; padding:6px 10px; background:#1f2937; border:1px solid #374151; border-radius:8px; color:#e5e7eb; cursor:pointer; font-size:12px; }
    @media (max-width: 760px) {
      .top-actions { display:none; }
      .menu-toggle { display:inline-flex; align-items:center; gap:8px; }
    }
    @media (min-width: 760px) { .row2 { display:grid; grid-template-columns:1fr 1fr; gap:10px; } }
  </style>
</head>
<body>
  <div class="wrap">
    <header class="bar">
      <div>
        <h1 class="brand">SysPetrosynergy</h1>
        <p class="sub">Bem-vindo, {{ user_name }}</p>
      </div>
      <button id="menu-toggle" class="menu-toggle" type="button">Menu</button>
      <div class="top-actions">
        <a class="hist-link" href="{{ url_for('dashboard_page') }}">Dashboard</a>
        <a class="hist-link calc-link" href="{{ url_for('calculadora_page') }}"><span class="calc-mini" aria-hidden="true">+</span>Calculadora</a>
        <a class="hist-link" href="{{ url_for('historico_page') }}"><span class="folder-mini" aria-hidden="true"></span>Historico</a>
        <a class="logout" href="{{ url_for('logout') }}">Sair</a>
      </div>
    </header>
    <div id="mobile-menu-backdrop" class="mobile-menu-backdrop"></div>
    <aside id="mobile-menu" class="mobile-menu" aria-hidden="true">
      <div class="mobile-menu-head">
        <strong>Menu</strong>
        <button id="mobile-menu-close" class="mobile-close" type="button">Fechar</button>
      </div>
      <nav class="mobile-actions">
        <a class="hist-link" href="{{ url_for('dashboard_page') }}">Dashboard</a>
        <a class="hist-link calc-link" href="{{ url_for('calculadora_page') }}"><span class="calc-mini" aria-hidden="true">+</span>Calculadora</a>
        <a class="hist-link" href="{{ url_for('historico_page') }}"><span class="folder-mini" aria-hidden="true"></span>Historico</a>
        <a class="logout" href="{{ url_for('logout') }}">Sair</a>
      </nav>
    </aside>

    <section class="card">
      <div style="display:flex; justify-content:flex-end; margin-bottom:8px;">
      
      </div>
      <h2 style="margin-top:0">Nova Medicao</h2>
      <form id="medicao-form" class="grid">
        <div class="row2">
          <div>
            <label for="campo_id">Campo de petroleo</label>
            <select id="campo_id" required></select>
          </div>
          <div>
            <label for="tanque_id">Tanque</label>
            <select id="tanque_id" required></select>
          </div>
        </div>
        <div class="row2">
          <div>
            <label for="data_medicao">Data</label>
            <input id="data_medicao" type="date" required />
          </div>
          <div>
            <label for="hora">Hora</label>
            <select id="hora" required></select>
          </div>
        </div>
        <div>
          <label for="medida">Medida</label>
          <input id="medida" type="number" step="0.01" placeholder="12345.67" required />
        </div>
        <div>
          <label for="situacao">Situacao</label>
          <select id="situacao" required>
            <option>Prod</option>
            <option>Disp</option>
            <option>Rece</option>
            <option>Rece tk1</option>
            <option>Rece tk2</option>
            <option>Rece tk5</option>
            <option>Rece tk6</option>
            <option>Rece cx API</option>
            <option>Rece carreta</option>
            <option>Forn</option>
            <option>Forn tk2</option>
            <option>Forn tk4</option>
            <option>Forn tk5</option>
            <option>Forn tk6</option>
            <option>Dren</option>
            <option>Dren car</option>
            <option>Dren carr</option>
            <option>Dren ct1</option>
            <option>Dren cx API</option>
            <option>Dren tk8</option>
            <option>Inj</option>
            <option>Vend</option>
          </select>
        </div>
        <div>
          <label for="observacao">Observacao (opcional)</label>
          <textarea id="observacao"></textarea>
        </div>
        <button type="submit">Salvar Medicao</button>
      </form>
      <div id="msg" class="msg"></div>
    </section>

    <section class="card" style="margin-top:14px;">
      <div class="bar" style="margin-bottom:10px;">
        <div>
          <h2 style="margin:0">Historico do Dia</h2>
          <p class="sub">Apenas movimentacoes de hoje na pagina principal</p>
        </div>
        <div style="display:flex; gap:8px; align-items:center;">
          <button id="btn-atualizar-historico" type="button" style="width:auto; padding:10px 14px;">Atualizar</button>
          <button id="btn-excluir-historico-geral" class="btn-del" type="button" style="width:auto; padding:10px 14px;">Lixeira Geral</button>
        </div>
      </div>
      <div id="historico-groups" class="historico-groups"></div>
    </section>
  </div>

  <div id="oil-tip" class="oil-tip">Ola, eu sou a OIL IA do Syspetrosynergy.</div>

  <button id="oil-fab" class="oil-fab" type="button" title="Abrir OIL">
    <span class="oil-icon" aria-hidden="true">oil_barrel</span>
  </button>

  <section id="oil-panel" class="oil-panel">
    <div class="oil-top">
      <h2 style="margin:0">OIL</h2>
      <button id="oil-close" class="oil-close" type="button">Fechar</button>
    </div>
    <p class="sub">Formato: <strong>tanque_ref medida HH:MM situacao [observacao]</strong></p>
    <form id="oil-form" class="grid">
      <div>
        <label for="oil_message">Mensagem OIL</label>
        <input id="oil_message" type="text" placeholder="tp40003 230 14:20 inj observacao opcional" required />
      </div>
      <button type="submit">Enviar via OIL</button>
    </form>
    <div id="oil-msg" class="msg"></div>
    <hr style="border-color:#334155; margin:12px 0;" />
    <h3 style="margin:0 0 6px; font-size:15px;">Tire duvidas com a OIL</h3>
    <form id="oil-help-form" class="grid">
      <div>
        <label for="oil_help_question">Pergunta</label>
        <input id="oil_help_question" type="text" placeholder="Ex: como registrar manobra?" />
      </div>
      <button type="submit">Perguntar para OIL</button>
    </form>
    <div id="oil-help-msg" class="msg"></div>
  </section>

<script>
  const campoSelect = document.getElementById("campo_id");
  const tanqueSelect = document.getElementById("tanque_id");
  const dataInput = document.getElementById("data_medicao");
  const horaInput = document.getElementById("hora");
  const menuToggleBtn = document.getElementById("menu-toggle");
  const mobileMenu = document.getElementById("mobile-menu");
  const mobileMenuBackdrop = document.getElementById("mobile-menu-backdrop");
  const mobileMenuCloseBtn = document.getElementById("mobile-menu-close");
  const oilFab = document.getElementById("oil-fab");
  const oilTip = document.getElementById("oil-tip");
  const oilPanel = document.getElementById("oil-panel");
  const oilCloseBtn = document.getElementById("oil-close");
  const oilForm = document.getElementById("oil-form");
  const oilInput = document.getElementById("oil_message");
  const oilHelpForm = document.getElementById("oil-help-form");
  const oilHelpInput = document.getElementById("oil_help_question");
  const historicoGroups = document.getElementById("historico-groups");
  const atualizarHistoricoBtn = document.getElementById("btn-atualizar-historico");
  const excluirHistoricoGeralBtn = document.getElementById("btn-excluir-historico-geral");
  const msgBox = document.getElementById("msg");
  const oilMsgBox = document.getElementById("oil-msg");
  const oilHelpMsgBox = document.getElementById("oil-help-msg");

  function buildHoraOptions() {
    horaInput.innerHTML = "";
    for (let h = 0; h < 24; h += 1) {
      for (let m = 0; m < 60; m += 15) {
        const hh = String(h).padStart(2, "0");
        const mm = String(m).padStart(2, "0");
        const value = hh + ":" + mm;
        const op = document.createElement("option");
        op.value = value;
        op.textContent = value;
        horaInput.appendChild(op);
      }
    }
  }

  function formatQuarterHour(dateObj) {
    const d = new Date(dateObj);
    d.setSeconds(0, 0);
    const m = d.getMinutes();
    const nextQuarter = Math.ceil(m / 15) * 15;
    if (nextQuarter === 60) {
      d.setHours(d.getHours() + 1);
      d.setMinutes(0);
    } else {
      d.setMinutes(nextQuarter);
    }
    return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
  }

  buildHoraOptions();
  dataInput.value = new Date().toISOString().slice(0, 10);
  horaInput.value = formatQuarterHour(new Date());

  function showMsg(text, ok) {
    msgBox.textContent = text;
    msgBox.className = "msg " + (ok ? "ok" : "error");
  }

  function showOilMsg(text, ok) {
    oilMsgBox.textContent = text;
    oilMsgBox.className = "msg " + (ok ? "ok" : "error");
  }

  function showOilHelpMsg(text, ok) {
    oilHelpMsgBox.textContent = text;
    oilHelpMsgBox.className = "msg " + (ok ? "ok" : "error");
  }

  function toggleMobileMenu(open) {
    if (!mobileMenu || !mobileMenuBackdrop) return;
    const shouldOpen = typeof open === "boolean" ? open : !mobileMenu.classList.contains("open");
    mobileMenu.classList.toggle("open", shouldOpen);
    mobileMenuBackdrop.classList.toggle("open", shouldOpen);
    mobileMenu.setAttribute("aria-hidden", shouldOpen ? "false" : "true");
    document.body.style.overflow = shouldOpen ? "hidden" : "";
  }

  function getLocalISODate() {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }

  function buildGroupTable(registros) {
    const wrap = document.createElement("div");
    wrap.className = "group-table-wrap";

    const table = document.createElement("table");
    table.className = "group-table";
    table.innerHTML = `
      <thead>
        <tr>
          <th>Data</th>
          <th>Hora</th>
          <th>Campo</th>
          <th>Tanque</th>
          <th>Medida</th>
          <th>SIT</th>
          <th>Operador</th>
          <th>Status</th>
          <th>Obs.</th>
          <th>Lixeira</th>
        </tr>
      </thead>
    `;
    const tbody = document.createElement("tbody");

    registros.forEach(item => {
      const tr = document.createElement("tr");
      const medida = Number(item.medida);
      const statusClass = item.status_envio === "enviado" ? "status-ok" : "status-erro";
      const statusText = item.status_envio === "enviado" ? "Enviado" : "Erro";
      const columns = [
        item.data_medicao || "",
        item.hora || "",
        item.campo_nome || "",
        item.tanque_nome || "",
        Number.isFinite(medida) ? medida.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "",
        item.situacao || "",
        item.operador || "",
        statusText,
        item.observacao || item.erro_envio || ""
      ];

      columns.forEach((value, idx) => {
        const td = document.createElement("td");
        td.textContent = value;
        if (idx === 7) td.className = statusClass;
        tr.appendChild(td);
      });

      const actionTd = document.createElement("td");
      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "btn-del";
      delBtn.textContent = "Excluir";
      delBtn.setAttribute("data-id", String(item.id || ""));
      actionTd.appendChild(delBtn);
      tr.appendChild(actionTd);

      tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    wrap.appendChild(table);
    return wrap;
  }

  function renderHistorico(registros) {
    historicoGroups.innerHTML = "";
    if (!Array.isArray(registros) || registros.length === 0) {
      const empty = document.createElement("div");
      empty.className = "sub";
      empty.textContent = "Sem medicoes de hoje.";
      historicoGroups.appendChild(empty);
      return;
    }

    const today = getLocalISODate();
    const hoje = registros.filter((item) => (item.data_medicao || "") === today);
    if (hoje.length === 0) {
      const empty = document.createElement("div");
      empty.className = "sub";
      empty.textContent = "Sem medicoes de hoje.";
      historicoGroups.appendChild(empty);
      return;
    }
    historicoGroups.appendChild(buildGroupTable(hoje));
  }

  async function deleteHistorico(id) {
    if (!id) return;
    const resp = await fetch(`/api/historico/${encodeURIComponent(id)}`, { method: "DELETE" });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      throw new Error(data.message || "Falha ao excluir medicao");
    }
  }

  async function deleteHistoricoCompleto() {
    const resp = await fetch("/api/historico", { method: "DELETE" });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      throw new Error(data.message || "Falha ao excluir historico completo");
    }
    return data;
  }

  async function loadHistorico() {
    try {
      const r = await fetch("/api/historico?limit=200");
      if (!r.ok) throw new Error("falha ao carregar historico");
      const data = await r.json();
      renderHistorico(data);
    } catch (err) {
      console.error(err);
    }
  }

  async function loadCampos() {
    const r = await fetch("/api/campos");
    const campos = await r.json();
    campoSelect.innerHTML = '<option value="">Selecione...</option>';
    campos.forEach(c => {
      const op = document.createElement("option");
      op.value = c.campo_id;
      op.textContent = c.campo_nome;
      campoSelect.appendChild(op);
    });
  }

  async function loadTanques(campoId) {
    tanqueSelect.innerHTML = '<option value="">Selecione...</option>';
    if (!campoId) return;
    const r = await fetch("/api/tanques?campo_id=" + encodeURIComponent(campoId));
    const tanques = await r.json();
    tanques.forEach(t => {
      const op = document.createElement("option");
      op.value = t.tanque_id;
      op.textContent = t.tanque_nome;
      tanqueSelect.appendChild(op);
    });
  }

  campoSelect.addEventListener("change", (e) => loadTanques(e.target.value));

  document.getElementById("medicao-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    showMsg("", true);
    const payload = {
      campo_id: campoSelect.value,
      tanque_id: tanqueSelect.value,
      data_medicao: dataInput.value,
      hora: document.getElementById("hora").value,
      medida: Number(document.getElementById("medida").value),
      situacao: document.getElementById("situacao").value,
      observacao: document.getElementById("observacao").value.trim()
    };

    const resp = await fetch("/api/medicoes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await resp.json();
    if (!resp.ok) {
      showMsg(data.message || "Erro ao salvar medicao", false);
      return;
    }

    document.getElementById("medida").value = "";
    document.getElementById("observacao").value = "";
    horaInput.value = formatQuarterHour(new Date());
    loadHistorico();
    const wa = data.whatsapp;
    if (wa && wa.enabled && wa.sent === false) {
      showMsg("Medicao salva, mas falhou envio para WhatsApp.", false);
      return;
    }
    showMsg("Medicao enviada com sucesso para a planilha e WhatsApp.", true);
  });

  oilForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    showOilMsg("", true);
    const payload = { message: oilInput.value.trim() };
    if (!payload.message) {
      showOilMsg("Informe a mensagem OIL.", false);
      return;
    }

    const resp = await fetch("/api/medicoes/oil", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      showOilMsg(data.message || "Falha no envio OIL", false);
      return;
    }

    oilInput.value = "";
    loadHistorico();
    const wa = data.whatsapp;
    if (wa && wa.enabled && wa.sent === false) {
      showOilMsg("OIL salvou na planilha, mas falhou no WhatsApp.", false);
      return;
    }
    showOilMsg("OIL enviada com sucesso para planilha e WhatsApp.", true);
  });

  oilHelpForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    showOilHelpMsg("", true);
    const question = oilHelpInput.value.trim();
    if (!question) {
      showOilHelpMsg("Digite sua duvida para a OIL.", false);
      return;
    }

    const resp = await fetch("/api/oil/help", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question })
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      showOilHelpMsg(data.message || "Falha ao consultar a OIL.", false);
      return;
    }
    showOilHelpMsg(data.answer || "Sem resposta da OIL.", true);
  });

  historicoGroups.addEventListener("click", async (e) => {
    const target = e.target.closest("button.btn-del");
    if (!target) return;
    const id = target.getAttribute("data-id");
    if (!id) return;
    if (!confirm("Deseja excluir esta manobra do historico?")) return;
    try {
      await deleteHistorico(id);
      await loadHistorico();
      showMsg("Manobra excluida do historico.", true);
    } catch (err) {
      showMsg(err.message || "Falha ao excluir manobra.", false);
    }
  });

  atualizarHistoricoBtn.addEventListener("click", () => loadHistorico());
  if (menuToggleBtn) {
    menuToggleBtn.addEventListener("click", () => toggleMobileMenu(true));
  }
  if (mobileMenuCloseBtn) {
    mobileMenuCloseBtn.addEventListener("click", () => toggleMobileMenu(false));
  }
  if (mobileMenuBackdrop) {
    mobileMenuBackdrop.addEventListener("click", () => toggleMobileMenu(false));
  }
  if (mobileMenu) {
    mobileMenu.addEventListener("click", (e) => {
      const link = e.target.closest("a");
      if (link) toggleMobileMenu(false);
    });
  }
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") toggleMobileMenu(false);
  });
  excluirHistoricoGeralBtn.addEventListener("click", async () => {
    const warn = "Deseja excluir TODO o historico salvo? Essa acao limpa historico e planilha.";
    if (!confirm(warn)) return;
    if (!confirm("Confirmacao final: excluir historico completo agora?")) return;
    try {
      const result = await deleteHistoricoCompleto();
      await loadHistorico();
      const deleted = Number(result && result.deleted);
      showMsg(
        Number.isFinite(deleted)
          ? `Historico completo excluido (${deleted} registros).`
          : "Historico completo excluido.",
        true
      );
    } catch (err) {
      showMsg(err.message || "Falha ao excluir historico completo.", false);
    }
  });
  oilFab.addEventListener("click", () => oilPanel.classList.toggle("open"));
  oilCloseBtn.addEventListener("click", () => oilPanel.classList.remove("open"));
  setTimeout(() => {
    if (oilTip) oilTip.style.display = "none";
  }, 60000);
  loadCampos();
  loadHistorico();
  setInterval(loadHistorico, 30000);
</script>
</body>
</html>
"""


def load_tanques():
    path = os.getenv("TANKS_JSON_PATH", "tanques.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    return DEFAULT_TANKS


def get_auth_config():
    raw_hash = os.getenv("DEFAULT_USER_PASSWORD_HASH", "").strip()
    # Accept values with optional surrounding quotes from .env editors.
    if raw_hash.startswith(("'", '"')) and raw_hash.endswith(("'", '"')) and len(raw_hash) >= 2:
        raw_hash = raw_hash[1:-1]

    return {
        "login": os.getenv("DEFAULT_USER_LOGIN", "operador").strip(),
        "name": os.getenv("DEFAULT_USER_NAME", "Operador de Campo"),
        "password_hash": raw_hash,
    }


def get_db_connection():
    conn = sqlite3.connect(HISTORY_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_history_db():
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS medicoes_historico (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                operador TEXT NOT NULL,
                campo_id TEXT NOT NULL,
                campo_nome TEXT NOT NULL,
                tanque_id TEXT NOT NULL,
                tanque_nome TEXT NOT NULL,
                sheet_tab TEXT NOT NULL,
                tanque_sheet_key TEXT,
                data_medicao TEXT NOT NULL,
                hora TEXT NOT NULL,
                boletim_data_ref TEXT NOT NULL,
                medida REAL NOT NULL,
                situacao TEXT NOT NULL,
                observacao TEXT NOT NULL DEFAULT '',
                status_envio TEXT NOT NULL,
                erro_envio TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                login TEXT NOT NULL UNIQUE,
                nome TEXT NOT NULL,
                senha_hash TEXT NOT NULL
            )
            """
        )


def get_user_by_login(login_value):
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT login, nome, senha_hash FROM usuarios WHERE lower(login)=lower(?) LIMIT 1",
            (login_value,),
        ).fetchone()
    return dict(row) if row else None


def create_user(login_value, nome, senha):
    senha_hash = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO usuarios (login, nome, senha_hash) VALUES (?, ?, ?)",
            (login_value.strip(), nome.strip(), senha_hash),
        )


def bootstrap_default_user():
    cfg = get_auth_config()
    if not cfg["login"] or not cfg["password_hash"]:
        return
    existing = get_user_by_login(cfg["login"])
    if existing:
        return
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO usuarios (login, nome, senha_hash) VALUES (?, ?, ?)",
            (cfg["login"], cfg["name"], cfg["password_hash"]),
        )


def save_medicao_history(tanque, payload, operador, boletim_date, status_envio, erro_envio=""):
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO medicoes_historico (
                operador, campo_id, campo_nome, tanque_id, tanque_nome,
                sheet_tab, tanque_sheet_key, data_medicao, hora, boletim_data_ref,
                medida, situacao, observacao, status_envio, erro_envio
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                operador,
                payload["campo_id"],
                tanque["campo_nome"],
                payload["tanque_id"],
                tanque["tanque_nome"],
                tanque.get("sheet_tab") or os.getenv("DEFAULT_REGISTROS_TAB", "Registros"),
                tanque.get("sheet_key", ""),
                payload["data_medicao"],
                payload["hora"],
                boletim_date.strftime("%Y-%m-%d"),
                float(payload["medida"]),
                payload["situacao"],
                payload.get("observacao", ""),
                status_envio,
                erro_envio,
            ),
        )


def fetch_medicao_history(limit=200):
    limit = max(1, min(int(limit), 500))
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                id, created_at, operador, campo_nome, tanque_nome, data_medicao,
                hora, boletim_data_ref, medida, situacao, observacao, status_envio, erro_envio
            FROM medicoes_historico
            ORDER BY data_medicao DESC, hora DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def fetch_dashboard_overview(hours=24, points_per_tank=24):
    hours = max(1, min(int(hours), 72))
    points_per_tank = max(6, min(int(points_per_tank), 96))
    now = datetime.now()
    start_time = now - timedelta(hours=hours)

    tanques = load_tanques()
    ordered_tanks = []
    by_key = {}
    fields = {}
    for t in tanques:
        key = (t["campo_id"], t["tanque_id"])
        by_key[key] = t
        ordered_tanks.append(key)
        if t["campo_id"] not in fields:
            fields[t["campo_id"]] = {"campo_id": t["campo_id"], "campo_nome": t["campo_nome"], "tanks": []}

    query_limit = max(500, len(ordered_tanks) * 120)
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                id, campo_id, campo_nome, tanque_id, tanque_nome, tanque_sheet_key,
                data_medicao, hora, boletim_data_ref, medida, situacao, operador, status_envio
            FROM medicoes_historico
            ORDER BY data_medicao DESC, hora DESC, id DESC
            LIMIT ?
            """,
            (query_limit,),
        ).fetchall()

    latest_map = {}
    points_map = {}

    for row in rows:
        item = dict(row)
        key = (item.get("campo_id"), item.get("tanque_id"))
        if key not in by_key:
            continue

        data_medicao = str(item.get("data_medicao") or "").strip()
        hora = str(item.get("hora") or "").strip()
        try:
            dt = datetime.strptime(f"{data_medicao} {hora}", "%Y-%m-%d %H:%M")
        except ValueError:
            continue

        item["timestamp"] = dt.strftime("%Y-%m-%d %H:%M")
        if key not in latest_map:
            latest_map[key] = item

        if dt < start_time:
            continue
        if key not in points_map:
            points_map[key] = []
        if len(points_map[key]) >= points_per_tank:
            continue
        points_map[key].append(
            {
                "timestamp": item["timestamp"],
                "data_medicao": data_medicao,
                "hora": hora,
                "medida": item.get("medida"),
                "situacao": item.get("situacao") or "",
            }
        )

    for key in ordered_tanks:
        t = by_key[key]
        latest = latest_map.get(key)
        points = list(reversed(points_map.get(key, [])))

        minutes_since_last = None
        status = "sem_dados"
        if latest:
            try:
                dt = datetime.strptime(latest["timestamp"], "%Y-%m-%d %H:%M")
                minutes_since_last = max(0, int((now - dt).total_seconds() // 60))
            except ValueError:
                minutes_since_last = None

        if minutes_since_last is not None:
            if minutes_since_last <= 45:
                status = "online"
            elif minutes_since_last <= 120:
                status = "atencao"
            else:
                status = "atrasado"

        fields[t["campo_id"]]["tanks"].append(
            {
                "tanque_id": t["tanque_id"],
                "tanque_nome": t["tanque_nome"],
                "sheet_key": t.get("sheet_key", ""),
                "status": status,
                "minutes_since_last": minutes_since_last,
                "latest": (
                    {
                        "timestamp": latest.get("timestamp"),
                        "data_medicao": latest.get("data_medicao"),
                        "hora": latest.get("hora"),
                        "medida": latest.get("medida"),
                        "situacao": latest.get("situacao"),
                        "operador": latest.get("operador"),
                    }
                    if latest
                    else None
                ),
                "points": points,
            }
        )

    field_list = list(fields.values())
    return {
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "hours_window": hours,
        "fields": field_list,
    }


def fetch_medicao_history_by_id(medicao_id):
    with get_db_connection() as conn:
        row = conn.execute(
            """
            SELECT
                id, status_envio, tanque_sheet_key, tanque_id, tanque_nome,
                boletim_data_ref, hora, medida, situacao
            FROM medicoes_historico
            WHERE id = ?
            LIMIT 1
            """,
            (int(medicao_id),),
        ).fetchone()
    return dict(row) if row else None


def fetch_all_medicao_history_for_delete():
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                id, status_envio, tanque_sheet_key, tanque_id, tanque_nome,
                boletim_data_ref, hora, medida, situacao
            FROM medicoes_historico
            ORDER BY id ASC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def delete_medicao_history(medicao_id):
    with get_db_connection() as conn:
        cur = conn.execute("DELETE FROM medicoes_historico WHERE id = ?", (int(medicao_id),))
        return cur.rowcount > 0


def delete_all_medicao_history():
    with get_db_connection() as conn:
        cur = conn.execute("DELETE FROM medicoes_historico")
        return max(cur.rowcount, 0)


def get_boletim_date(data_medicao=None, hora=None, now=None):
    current = now or datetime.now()
    parsed_date = None
    parsed_time = None
    if data_medicao and hora:
        try:
            parsed_date = datetime.strptime(str(data_medicao).strip(), "%Y-%m-%d").date()
            parsed_time = datetime.strptime(str(hora).strip(), "%H:%M").time()
            current = datetime.combine(parsed_date, parsed_time)
        except ValueError:
            current = now or datetime.now()
    try:
        cutoff_hour = int(os.getenv("BOLETIM_CUTOFF_HOUR", "12"))
    except ValueError:
        cutoff_hour = 12
    cutoff_hour = max(0, min(23, cutoff_hour))

    # Boletim e rotulado pela data de fechamento:
    # 12:00 do dia anterior ate 11:59 do dia atual = boletim do dia atual.
    if current.hour >= cutoff_hour:
        return current.date() + timedelta(days=1)
    return current.date()


def append_to_sheet(tanque, payload, operador):
    apps_script_url = os.getenv("APPS_SCRIPT_WEB_APP_URL", "").strip()
    if not apps_script_url:
        raise RuntimeError("APPS_SCRIPT_WEB_APP_URL nao configurado")

    boletim_date = get_boletim_date(payload.get("data_medicao"), payload.get("hora"))
    body = {
        "tanque_id": tanque.get("tanque_id", ""),
        "sheet_tab": tanque.get("sheet_tab") or os.getenv("DEFAULT_REGISTROS_TAB", "Registros"),
        "boletim_data_ref": boletim_date.strftime("%Y-%m-%d"),
        "hora": payload["hora"],
        "campo_nome": tanque["campo_nome"],
        "tanque_nome": tanque["tanque_nome"],
        "medida": payload["medida"],
        "situacao": payload["situacao"],
        "observacao": payload.get("observacao", ""),
        "operador": operador,
        "tanque_sheet_key": tanque.get("sheet_key", ""),
    }
    req = urllib.request.Request(
        apps_script_url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            if not raw:
                return
            raw = raw.strip()
            if not raw.startswith("{"):
                message = extract_apps_script_error(raw)
                raise RuntimeError(f"Apps Script retornou HTML: {message}")
            data = json.loads(raw)
            if not data.get("ok", False):
                raise RuntimeError(data.get("error", "Apps Script retornou erro"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Apps Script HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Falha de conexao com Apps Script: {exc.reason}") from exc


def delete_from_sheet(history_item):
    apps_script_url = os.getenv("APPS_SCRIPT_WEB_APP_URL", "").strip()
    if not apps_script_url:
        raise RuntimeError("APPS_SCRIPT_WEB_APP_URL nao configurado")

    body = {
        "action": "delete",
        "tanque_sheet_key": history_item.get("tanque_sheet_key") or "",
        "tanque_id": history_item.get("tanque_id") or "",
        "tanque_nome": history_item.get("tanque_nome") or "",
        "boletim_data_ref": history_item.get("boletim_data_ref") or "",
        "hora": history_item.get("hora") or "",
        "medida": history_item.get("medida"),
        "situacao": history_item.get("situacao") or "",
    }
    req = urllib.request.Request(
        apps_script_url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="ignore").strip()
            if not raw:
                raise RuntimeError("Apps Script retornou resposta vazia")
            if not raw.startswith("{"):
                message = extract_apps_script_error(raw)
                raise RuntimeError(f"Apps Script retornou HTML: {message}")
            data = json.loads(raw)
            if not data.get("ok", False):
                raise RuntimeError(data.get("error", "Apps Script retornou erro"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Apps Script HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Falha de conexao com Apps Script: {exc.reason}") from exc


def extract_apps_script_error(raw_html):
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = " ".join(text.split())
    marker = "Os dados inseridos na célula"
    if marker in text:
        return text[text.find(marker) :][:250]
    return text[:250] if text else "resposta invalida"


def normalize_token(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").strip().lower())


def normalize_situacao(raw_value):
    value = str(raw_value or "").strip()
    if not value:
        return ""

    normalized = value.lower()
    alias_map = {
        "inj": "Inj",
        "prod": "Prod",
        "disp": "Disp",
        "vend": "Vend",
        "rece": "Rece",
        "forn": "Forn",
        "dren": "Dren",
    }
    if normalized in alias_map:
        return alias_map[normalized]

    for item in SITUACAO_OPTIONS:
        if item.lower() == normalized:
            return item
    return value


def find_tanque_by_ref(tanques, ref_token):
    target = normalize_token(ref_token)
    if not target:
        return None

    for tanque in tanques:
        candidates = {
            normalize_token(tanque.get("tanque_id")),
            normalize_token(tanque.get("sheet_key")),
            normalize_token(tanque.get("tanque_nome")),
        }
        if target in candidates:
            return tanque
    return None


def parse_oil_message(raw_message, tanques):
    text = str(raw_message or "").strip()
    if not text:
        return False, "Mensagem OIL vazia", None

    parts = text.split()
    if len(parts) < 4:
        return False, "Formato OIL invalido. Use: <tanque> <medida> <HH:MM> <situacao> [obs]", None

    tanque_ref, medida_raw, hora_raw, situacao_raw = parts[0], parts[1], parts[2], parts[3]
    observacao = " ".join(parts[4:]).strip()

    tanque = find_tanque_by_ref(tanques, tanque_ref)
    if not tanque:
        return False, "Tanque nao encontrado. Use tanque_id, sheet_key ou nome do tanque.", None

    medida_raw = medida_raw.replace(",", ".")
    try:
        medida_value = float(medida_raw)
    except ValueError:
        return False, "Medida invalida na mensagem OIL", None

    if not re.fullmatch(r"\d{2}:\d{2}", hora_raw):
        return False, "Hora invalida na mensagem OIL. Use HH:MM", None

    payload = {
        "campo_id": tanque["campo_id"],
        "tanque_id": tanque["tanque_id"],
        "data_medicao": datetime.now().strftime("%Y-%m-%d"),
        "hora": hora_raw,
        "medida": medida_value,
        "situacao": normalize_situacao(situacao_raw),
        "observacao": observacao,
    }
    return True, "", payload


def get_oil_help_answer(question):
    text = str(question or "").strip().lower()
    if not text:
        return (
            "Posso ajudar com: registro manual, formato OIL, situacoes aceitas, historico e envio WhatsApp. "
            "Pergunte por exemplo: 'como registrar manobra?'."
        )

    scored = []
    for topic in OIL_HELP_TOPICS:
        score = sum(1 for kw in topic["keywords"] if kw in text)
        if score > 0:
            scored.append((score, topic["answer"]))

    if not scored:
        return (
            "Nao encontrei essa duvida na base local da OIL. "
            "Tente termos como: registrar manobra, formato OIL, situacao, historico ou WhatsApp."
        )

    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def notify_whatsapp_group(tanque, payload, operador, origem):
    webhook_url = os.getenv("WHATSAPP_GROUP_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return {"enabled": False, "sent": False, "detail": "webhook desabilitado"}

    webhook_token = os.getenv("WHATSAPP_GROUP_WEBHOOK_TOKEN", "").strip()
    timeout_sec = int(os.getenv("WHATSAPP_GROUP_TIMEOUT_SEC", "12"))
    origem_label = "oil" if origem == "oil" else "manual"
    observacao = str(payload.get("observacao", "")).strip()
    text = (
        f"[SysPetro] [{origem_label}] {tanque['campo_nome']} / {tanque['tanque_nome']} | "
        f"{payload['data_medicao']} {payload['hora']} | medida {payload['medida']} | "
        f"situacao {payload['situacao']} | operador {operador}"
    )
    if observacao:
        text += f" | obs: {observacao}"

    data = json.dumps(
        {
            "text": text,
            "origem": origem_label,
            "operador": operador,
            "campo_id": payload["campo_id"],
            "tanque_id": payload["tanque_id"],
            "data_medicao": payload["data_medicao"],
            "hora": payload["hora"],
            "medida": payload["medida"],
            "situacao": payload["situacao"],
            "observacao": observacao,
        }
    ).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    if webhook_token:
        headers["Authorization"] = f"Bearer {webhook_token}"

    req = urllib.request.Request(webhook_url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as response:
            body = response.read().decode("utf-8", errors="ignore")
            if 200 <= response.status < 300:
                return {"enabled": True, "sent": True, "detail": body[:250]}
            return {"enabled": True, "sent": False, "detail": f"HTTP {response.status}: {body[:250]}"}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        return {"enabled": True, "sent": False, "detail": f"HTTP {exc.code}: {detail[:250]}"}
    except Exception as exc:
        return {"enabled": True, "sent": False, "detail": str(exc)[:250]}


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_login"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


def unauthorized_json():
    return jsonify({"message": "Nao autenticado"}), 401


def validate_medicao(data):
    required_fields = ["campo_id", "tanque_id", "data_medicao", "hora", "medida", "situacao"]
    for field in required_fields:
        if field not in data or data[field] in (None, ""):
            return False, f"Campo obrigatorio: {field}"

    try:
        float(data["medida"])
    except (TypeError, ValueError):
        return False, "medida deve ser numerica"

    hora = str(data.get("hora", "")).strip()
    if not re.fullmatch(r"\d{2}:\d{2}", hora):
        return False, "hora deve estar no formato HH:MM"
    try:
        hora_dt = datetime.strptime(hora, "%H:%M")
    except ValueError:
        return False, "hora invalida"
    if hora_dt.minute % 15 != 0:
        return False, "hora deve ser em intervalos de 15 minutos (00, 15, 30, 45)"

    data_medicao = str(data.get("data_medicao", "")).strip()
    try:
        datetime.strptime(data_medicao, "%Y-%m-%d")
    except ValueError:
        return False, "data_medicao deve estar no formato YYYY-MM-DD"

    data["situacao"] = str(data["situacao"]).strip()
    if data["situacao"].lower() == "inj":
        data["situacao"] = "Inj"

    allowed = set(SITUACAO_OPTIONS)
    if data["situacao"] not in allowed:
        return False, "situacao invalida"

    return True, ""


def process_medicao_payload(payload, operador, origem="manual"):
    ok, msg = validate_medicao(payload)
    if not ok:
        return jsonify({"message": msg}), 400

    tanques = load_tanques()
    tanque = next(
        (
            t
            for t in tanques
            if t["campo_id"] == payload["campo_id"] and t["tanque_id"] == payload["tanque_id"]
        ),
        None,
    )

    if not tanque:
        return jsonify({"message": "Tanque nao encontrado para o campo selecionado"}), 404

    boletim_date = get_boletim_date(payload.get("data_medicao"), payload.get("hora"))

    try:
        payload["medida"] = float(payload["medida"])
        append_to_sheet(tanque, payload, operador)
        save_medicao_history(tanque, payload, operador, boletim_date, status_envio="enviado")
        wa_result = notify_whatsapp_group(tanque, payload, operador, origem)

        if wa_result["enabled"] and not wa_result["sent"]:
            app.logger.warning("Falha no envio WhatsApp: %s", wa_result["detail"])
            return (
                jsonify(
                    {
                        "message": "Medicao registrada na planilha, mas o envio para WhatsApp falhou",
                        "whatsapp": wa_result,
                    }
                ),
                201,
            )

        return jsonify({"message": "Medicao registrada com sucesso", "whatsapp": wa_result}), 201
    except Exception as exc:
        try:
            save_medicao_history(
                tanque,
                payload,
                operador,
                boletim_date,
                status_envio="erro",
                erro_envio=str(exc)[:400],
            )
        except Exception:
            app.logger.exception("Falha ao salvar medicao no historico")
        app.logger.exception("Falha ao enviar para planilha")
        return jsonify({"message": f"Falha ao enviar para planilha: {exc}"}), 500


init_history_db()
bootstrap_default_user()


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "SysPetro Flask"})


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if session.get("user_login"):
            return redirect(url_for("home"))
        return render_template_string(LOGIN_TEMPLATE, error="")

    login_value = request.form.get("login", "").strip().lower()
    senha_value = request.form.get("senha", "")
    user = get_user_by_login(login_value)
    if not user:
        return render_template_string(LOGIN_TEMPLATE, error="Login ou senha invalidos")

    valid = bcrypt.checkpw(senha_value.encode("utf-8"), user["senha_hash"].encode("utf-8"))
    if not valid:
        return render_template_string(LOGIN_TEMPLATE, error="Login ou senha invalidos")

    session["user_login"] = user["login"]
    session["user_name"] = user["nome"]
    return redirect(url_for("home"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template_string(REGISTER_TEMPLATE, error="", success="")

    name = request.form.get("name", "").strip()
    login_value = request.form.get("login", "").strip().lower()
    senha = request.form.get("senha", "")
    confirmar = request.form.get("confirmar_senha", "")

    if not name or not login_value or not senha:
        return render_template_string(REGISTER_TEMPLATE, error="Preencha todos os campos obrigatorios", success="")
    if len(senha) < 6:
        return render_template_string(REGISTER_TEMPLATE, error="Senha deve ter pelo menos 6 caracteres", success="")
    if senha != confirmar:
        return render_template_string(REGISTER_TEMPLATE, error="As senhas nao conferem", success="")
    if get_user_by_login(login_value):
        return render_template_string(REGISTER_TEMPLATE, error="Login ja cadastrado", success="")

    try:
        create_user(login_value, name, senha)
        return render_template_string(
            REGISTER_TEMPLATE,
            error="",
            success="Conta criada com sucesso. Agora voce pode entrar no login.",
        )
    except Exception:
        app.logger.exception("Falha ao registrar usuario")
        return render_template_string(REGISTER_TEMPLATE, error="Falha ao criar conta", success="")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def home():
    return render_template_string(APP_TEMPLATE, user_name=session.get("user_name", "Operador"))


@app.route("/historico")
@login_required
def historico_page():
    return render_template("historico.html", user_name=session.get("user_name", "Operador"))


@app.route("/calculadora")
@login_required
def calculadora_page():
    return render_template("calculadora.html", user_name=session.get("user_name", "Operador"))


@app.route("/dashboard")
@login_required
def dashboard_page():
    return render_template("dashboard.html", user_name=session.get("user_name", "Operador"))


@app.route("/api/campos")
def api_campos():
    if not session.get("user_login"):
        return unauthorized_json()

    tanques = load_tanques()
    unique = {}
    for item in tanques:
        if item["campo_id"] not in unique:
            unique[item["campo_id"]] = {
                "campo_id": item["campo_id"],
                "campo_nome": item["campo_nome"],
            }
    return jsonify(list(unique.values()))


@app.route("/api/tanques")
def api_tanques():
    if not session.get("user_login"):
        return unauthorized_json()

    campo_id = request.args.get("campo_id", "").strip()
    if not campo_id:
        return jsonify({"message": "campo_id e obrigatorio"}), 400

    tanques = [t for t in load_tanques() if t["campo_id"] == campo_id]
    return jsonify(tanques)


@app.route("/api/historico", methods=["GET", "DELETE"])
def api_historico():
    if not session.get("user_login"):
        return unauthorized_json()

    if request.method == "DELETE":
        try:
            records = fetch_all_medicao_history_for_delete()
            if not records:
                return jsonify({"message": "Historico ja esta vazio", "deleted": 0}), 200

            for item in records:
                if item.get("status_envio") == "enviado":
                    delete_from_sheet(item)

            deleted_count = delete_all_medicao_history()
            return jsonify({"message": "Historico completo excluido com sucesso", "deleted": deleted_count}), 200
        except Exception as exc:
            app.logger.exception("Falha ao excluir historico completo")
            return jsonify({"message": f"Falha ao excluir historico completo: {exc}"}), 500

    limit_raw = request.args.get("limit", "200").strip()
    try:
        limit = int(limit_raw)
    except ValueError:
        return jsonify({"message": "limit invalido"}), 400

    try:
        return jsonify(fetch_medicao_history(limit))
    except Exception as exc:
        app.logger.exception("Falha ao carregar historico")
        return jsonify({"message": f"Falha ao carregar historico: {exc}"}), 500


@app.route("/api/dashboard/overview")
def api_dashboard_overview():
    if not session.get("user_login"):
        return unauthorized_json()

    hours_raw = request.args.get("hours", "24").strip()
    points_raw = request.args.get("points", "24").strip()
    try:
        hours = int(hours_raw)
        points = int(points_raw)
    except ValueError:
        return jsonify({"message": "Parametros invalidos"}), 400

    try:
        return jsonify(fetch_dashboard_overview(hours=hours, points_per_tank=points))
    except Exception as exc:
        app.logger.exception("Falha ao carregar dashboard")
        return jsonify({"message": f"Falha ao carregar dashboard: {exc}"}), 500


@app.route("/api/historico/<int:medicao_id>", methods=["DELETE"])
def api_delete_historico(medicao_id):
    if not session.get("user_login"):
        return unauthorized_json()

    try:
        record = fetch_medicao_history_by_id(medicao_id)
        if not record:
            return jsonify({"message": "Manobra nao encontrada"}), 404

        if record.get("status_envio") == "enviado":
            delete_from_sheet(record)

        deleted = delete_medicao_history(medicao_id)
        if not deleted:
            return jsonify({"message": "Falha ao excluir manobra no historico local"}), 500
        return jsonify({"message": "Manobra excluida com sucesso"})
    except Exception as exc:
        app.logger.exception("Falha ao excluir manobra do historico")
        return jsonify({"message": f"Falha ao excluir manobra: {exc}"}), 500


@app.route("/api/medicoes", methods=["POST"])
def api_medicoes():
    if not session.get("user_login"):
        return unauthorized_json()

    payload = request.get_json(silent=True) or {}
    operador = session.get("user_name", "Operador")
    return process_medicao_payload(payload, operador, origem="manual")


@app.route("/api/medicoes/oil", methods=["POST"])
def api_medicoes_oil():
    if not session.get("user_login"):
        return unauthorized_json()

    body = request.get_json(silent=True) or {}
    raw_message = str(body.get("message", "")).strip()
    tanques = load_tanques()
    ok, err, payload = parse_oil_message(raw_message, tanques)
    if not ok:
        return jsonify({"message": err}), 400

    operador = session.get("user_name", "Operador")
    return process_medicao_payload(payload, operador, origem="oil")


@app.route("/api/oil/help", methods=["POST"])
def api_oil_help():
    if not session.get("user_login"):
        return unauthorized_json()

    body = request.get_json(silent=True) or {}
    question = str(body.get("question", "")).strip()
    answer = get_oil_help_answer(question)
    return jsonify({"answer": answer}), 200


def run_hash_mode(password):
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    print(hashed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SysPetro Flask app")
    parser.add_argument("--hash", dest="hash_password", help="Gera hash bcrypt para senha")
    args = parser.parse_args()

    if args.hash_password:
        run_hash_mode(args.hash_password)
    else:
        app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
