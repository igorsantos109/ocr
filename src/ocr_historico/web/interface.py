"""Frontend da estação de revisão: app de página única embarcado.

HTML + CSS + JS sem dependências externas (funciona offline, sem CDN).
Identidade visual OCR Studio (fluxo ABBYY × paleta Google Colab), ligado às
APIs reais do backend (/api/documentos, /api/revisao, /api/pagina, ...).
Mantém as strings `/api/documentos` e `name="viewport"` exigidas pelos testes,
bem como todos os IDs usados pelo teste de navegador headless.
"""

from __future__ import annotations

# ruff: noqa: E501 - template HTML/JS embarcado prioriza legibilidade das strings

PAGINA_HTML = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OCR STUDIO V1 — estação de revisão local</title>
<style>
/* ===== Tokens Google Colab ===== */
:root {
  --colab-orange: #F9AB00; --colab-orange-dark: #F29900; --colab-orange-soft: #FFF8E1;
  --colab-blue: #1A73E8; --bg: #FFFFFF; --surface: #F8F9FA; --border: #DADCE0;
  --text: #3C4043; --text-2: #5F6368; --success: #188038; --error: #D93025;
  --warn-soft: #FEEFC3; --mono-bg: #F7F7F7; --raio: 8px;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
  font-family: Roboto, 'Helvetica Neue', Arial, Helvetica, sans-serif; font-size: 14px; line-height: 1.5; }
:focus-visible { outline: 2px solid var(--colab-blue); outline-offset: 2px; border-radius: 4px; }
.container { max-width: 1200px; margin: 0 auto; padding: 0 24px; }

/* ===== 1. Barra superior (64px) ===== */
.topo { position: sticky; top: 0; z-index: 20; background: #fff; border-bottom: 1px solid var(--border); }
.topo .container { display: flex; align-items: center; gap: 24px; height: 64px; }
.marca { display: flex; align-items: center; gap: 10px; font-size: 18px; font-weight: 500; white-space: nowrap; }
.marca .logo-mark { width: 34px; height: 34px; border-radius: 8px; background: var(--colab-orange);
  display: inline-flex; align-items: center; justify-content: center; color: #202124; font-weight: 700; font-size: 15px; }
.marca small { display: block; font-size: 11px; font-weight: 400; color: var(--text-2); letter-spacing: .02em; }
.tabs { display: flex; gap: 4px; flex: 1; align-self: stretch; align-items: stretch; }
.tabs button { background: none; border: none; border-bottom: 3px solid transparent; padding: 0 14px;
  font-size: 14px; font-weight: 500; color: var(--text-2); cursor: pointer; font-family: inherit; }
.tabs button:hover { color: var(--text); }
.tabs button.active { color: var(--text); border-bottom-color: var(--colab-orange); }
.topo input[type=search], .topo select { background: var(--surface); color: var(--text);
  border: 1px solid var(--border); border-radius: 6px; padding: 7px 10px; font-size: 13px; font-family: inherit; }
.topo input[type=search] { width: 13rem; }
.topo select { max-width: 11rem; }
.pilula { display: inline-block; padding: 3px 12px; border-radius: 12px; font-size: 12px; font-weight: 500;
  border: 1px solid var(--border); background: var(--surface); color: var(--text-2); white-space: nowrap; }
.pilula.llm-ok { border-color: var(--success); color: var(--success); background: #E6F4EA; }
.pilula.llm-off { color: var(--text-2); }
.quota { background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
  padding: 5px 12px; font-size: 12px; color: var(--text-2); white-space: nowrap; }
.mini-stats { display: flex; gap: .6rem; font-size: .8rem; color: var(--text-2); white-space: nowrap; }
.mini-stats strong { color: var(--text); }

/* ===== 2. Barra de ferramentas + progresso (estilo Colab) ===== */
.toolbar { background: var(--surface); border-bottom: 1px solid var(--border); padding: 8px 0; }
.toolbar .container { display: flex; gap: 8px; flex-wrap: wrap; }
.tool-btn { display: inline-flex; align-items: center; gap: 6px; background: transparent;
  border: 1px solid transparent; border-radius: 6px; padding: 6px 12px; font-size: 13px;
  color: var(--text); cursor: pointer; font-family: inherit; }
.tool-btn:hover { background: #fff; border-color: var(--border); box-shadow: 0 1px 3px rgba(60,64,67,.15); }
.progress-track { height: 4px; background: #eee; }
.progress-track.idle .progress-bar { animation: none; width: 0; }
.progress-bar { height: 4px; width: 38%; background: var(--colab-orange); border-radius: 2px;
  animation: slide 2.2s ease-in-out infinite; }
@keyframes slide { 0% { margin-left: 0; } 50% { margin-left: 62%; } 100% { margin-left: 0; } }

/* ===== 3. Stepper do fluxo ===== */
.stepper { display: flex; align-items: center; justify-content: center; padding: 26px 0 6px; flex-wrap: wrap; }
.step { display: flex; align-items: center; gap: 8px; color: var(--text-2); font-size: 13px; font-weight: 500; }
.step .num { width: 26px; height: 26px; border-radius: 50%; border: 2px solid var(--border);
  display: inline-flex; align-items: center; justify-content: center; font-size: 12px; background: #fff; }
.step.active { color: var(--text); }
.step.active .num { background: var(--colab-orange); border-color: var(--colab-orange); color: #202124; }
.step.done .num { background: var(--success); border-color: var(--success); color: #fff; }
.step-line { width: 64px; height: 2px; background: var(--border); margin: 0 12px; }

/* ===== Cartões ===== */
.card { background: #fff; border: 1px solid var(--border); border-radius: var(--raio); margin: 20px 0; }
.card:hover { box-shadow: 0 1px 3px rgba(60,64,67,.2); }
.card-head { padding: 14px 20px; border-bottom: 1px solid var(--border); font-size: 15px; font-weight: 500;
  display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.card-body { padding: 20px; }
button, .btn { font-size: 13px; padding: 7px 14px; border-radius: var(--raio); cursor: pointer;
  border: 1px solid var(--border); background: #fff; color: var(--text); font-family: inherit; }
button:hover { box-shadow: 0 1px 3px rgba(60,64,67,.25); }
button.primario, .btn-primary { background: var(--colab-orange); border: none; color: #202124; font-weight: 500;
  border-radius: var(--raio); padding: 10px 22px; font-size: 14px; cursor: pointer; font-family: inherit; }
button.primario:hover, .btn-primary:hover { background: var(--colab-orange-dark); }
button.primario.sujo { box-shadow: 0 0 0 3px #F9AB0055; }
button:disabled { opacity: .45; cursor: wait; }
.btn-outline { background: #fff; color: var(--colab-blue); border: 1px solid var(--colab-blue);
  border-radius: var(--raio); padding: 7px 16px; font-size: 13px; font-weight: 500; cursor: pointer; font-family: inherit; }
.btn-outline:hover { background: #F6FAFF; }

/* ===== 4. Zona de upload ===== */
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden;
  clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
.dropzone { display: block; border: 2px dashed var(--border); border-radius: 12px; padding: 44px 24px; text-align: center;
  background: #fff; transition: border-color .15s, background .15s; cursor: pointer; }
.dropzone:hover, .dropzone.dragover { border-color: var(--colab-orange); background: var(--colab-orange-soft); }
.dropzone h2 { font-size: 18px; font-weight: 500; margin: 12px 0 6px; }
.dropzone p { color: var(--text-2); font-size: 13px; margin-bottom: 16px; }
.job { border: 1px solid var(--border); border-radius: var(--raio); padding: 14px 16px; margin: 12px 0 0; background: var(--surface); }
.job .job-head { display: flex; justify-content: space-between; gap: 8px; align-items: center; flex-wrap: wrap; }
.job-bar { height: 8px; background: #eee; border-radius: 4px; overflow: hidden; margin: 10px 0; }
.job-bar > i { display: block; height: 100%; background: var(--colab-orange); width: 0; transition: width .25s; }
.job-log { max-height: 8rem; overflow-y: auto; font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 12px;
  background: #fff; border: 1px solid var(--border); border-radius: 6px; padding: 8px; margin: 8px 0 0; color: var(--text-2); }
.job-log div { padding: 1px 0; }
.file-list { list-style: none; margin: 12px auto 0; padding: 0; font-size: 13px; color: var(--text-2); max-width: 32rem; text-align: left; }
.file-list li { padding: 3px 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* ===== 5. Configuração ===== */
.section-label { font-size: 13px; font-weight: 500; color: var(--text-2); margin: 18px 0 10px;
  text-transform: uppercase; letter-spacing: .4px; }
.section-label:first-child { margin-top: 0; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { border: 1px solid var(--border); border-radius: 16px; padding: 6px 16px; font-size: 13px;
  cursor: pointer; background: #fff; color: var(--text); user-select: none; }
.chip:hover { border-color: var(--colab-orange); }
.chip.selected { border-color: var(--colab-orange); background: var(--colab-orange-soft); font-weight: 500; }
.formats { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; }
.fmt { border: 1px solid var(--border); border-radius: var(--raio); padding: 14px; display: flex;
  align-items: center; gap: 10px; cursor: pointer; background: #fff; font-size: 13px; }
.fmt:hover { box-shadow: 0 1px 3px rgba(60,64,67,.25); }
.fmt.selected { border: 2px solid var(--colab-orange); padding: 13px; box-shadow: 0 1px 3px rgba(60,64,67,.25); }
.fmt-badge { width: 36px; height: 36px; border-radius: 6px; display: inline-flex; align-items: center;
  justify-content: center; font-size: 10px; font-weight: 700; color: #fff; flex-shrink: 0; }
.fmt small { display: block; color: var(--text-2); font-size: 11px; margin-top: 2px; }
.b-docx { background: #1A73E8; } .b-pdf { background: #D93025; } .b-txt { background: #5F6368; }
.b-xlsx { background: #188038; } .b-epub { background: #9334E6; } .b-fb2 { background: #E8710A; }
.toggles { display: flex; flex-wrap: wrap; gap: 18px; }
.toggle { display: flex; align-items: center; gap: 8px; font-size: 13px; cursor: pointer; }
.toggle input { accent-color: var(--colab-orange); width: 16px; height: 16px; cursor: pointer; }
.engine-panel { margin-top: 18px; border: 1px solid var(--border); border-radius: var(--raio); padding: 14px 16px;
  background: linear-gradient(135deg, #fff 0%, #FFF8E1 100%); }
.engine-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.engine-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.engine-head strong { font-size: 14px; }
.engine-status { margin-left: 8px; }
.engine-panel p { margin: 7px 0; color: var(--text-2); font-size: 13px; }
.engine-meta { display: flex; gap: 8px; flex-wrap: wrap; font-size: 12px; color: var(--text-2); }
.engine-meta span { border: 1px solid var(--border); border-radius: 12px; padding: 3px 9px; background: #fff; }
.engine-panel.indisponivel { background: #FFF8F7; border-color: #F6AEA8; }
.visual-quick { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;
  margin: 0 16px 12px; padding: 10px 12px; border: 1px solid #DADCE0; border-radius: var(--raio); background: #F8F9FA; }
.visual-quick strong { display: block; font-size: 13px; }
.visual-quick span { color: var(--text-2); font-size: 12px; }
.visual-quick-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.visual-quick-actions button { white-space: nowrap; }

/* ===== 6. Fila / tabela de documentos ===== */
.table-wrap { overflow-x: auto; }
table.docs { width: 100%; border-collapse: collapse; min-width: 720px; }
table.docs th { text-align: left; font-size: 12px; color: var(--text-2); font-weight: 500; padding: 10px 16px;
  border-bottom: 1px solid var(--border); text-transform: uppercase; letter-spacing: .4px; }
table.docs td { padding: 12px 16px; border-bottom: 1px solid var(--border); font-size: 13px; vertical-align: middle; }
table.docs tr:last-child td { border-bottom: none; }
table.docs tbody tr:hover { background: var(--surface); }
.thumb { width: 34px; height: 44px; border: 1px solid var(--border); border-radius: 4px;
  background: linear-gradient(#fff 60%, var(--surface)); display: inline-flex; align-items: center;
  justify-content: center; font-size: 9px; font-weight: 700; color: var(--text-2); }
.st { font-size: 12px; font-weight: 500; padding: 3px 12px; border-radius: 12px; border: 1px solid var(--border);
  white-space: nowrap; display: inline-block; }
.st-concluido, .st-revisada, .st-treinamento { color: var(--success); border-color: var(--success); background: #E6F4EA; }
.st-erro, .st-alta, .st-ilegivel { color: var(--error); border-color: var(--error); background: #FCE8E6; }
.st-parcial, .st-média { color: #B06000; border-color: var(--colab-orange); background: var(--colab-orange-soft); }
.st-aguardando_ocr, .st-pendente, .st-baixa { color: var(--text-2); background: var(--surface); }
.row-actions { display: flex; gap: 4px; }
.icon-btn { border: none; background: transparent; border-radius: 50%; width: 30px; height: 30px; cursor: pointer;
  color: var(--text-2); font-size: 14px; display: inline-flex; align-items: center; justify-content: center; padding: 0; }
.icon-btn:hover { background: var(--surface); color: var(--text); box-shadow: none; }
.cards-mobile { display: none; }

/* ===== Painel: cartões, distribuição, fila de linhas ===== */
.corpo { display: grid; grid-template-columns: 19rem 1fr; gap: 0; align-items: start; }
.lateral { border: 1px solid var(--border); border-radius: var(--raio); background: #fff; padding: 14px;
  overflow-y: auto; max-height: 70vh; position: sticky; top: 150px; }
.lateral h2 { font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: var(--text-2); margin: .2rem 0 .6rem; }
.doc { display: block; width: 100%; text-align: left; background: transparent; color: var(--text);
  border: 1px solid transparent; border-radius: var(--raio); padding: .55rem .6rem; cursor: pointer; margin-bottom: .25rem; }
.doc:hover { background: var(--surface); box-shadow: none; }
.doc.ativo { background: var(--colab-orange-soft); border-color: var(--colab-orange); }
.doc .nome { display: block; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
.doc .meta { display: flex; gap: .4rem; align-items: center; font-size: 12px; color: var(--text-2); margin-top: .25rem; flex-wrap: wrap; }
.principal { padding: 0 0 0 20px; min-width: 0; }
.cartoes { display: grid; grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr)); gap: 12px; margin-bottom: 16px; }
.cartao { background: #fff; border: 1px solid var(--border); border-radius: var(--raio); padding: 14px 16px; }
.cartao strong { display: block; font-size: 26px; font-weight: 500; color: var(--text); }
.cartao span { font-size: 12px; color: var(--text-2); }
.barra-dist { display: flex; height: 10px; border-radius: 5px; overflow: hidden; margin: 8px 0 12px; background: var(--surface); border: 1px solid var(--border); }
.barra-dist i { display: block; height: 100%; }
.secao { margin-bottom: 20px; }
.secao > h2 { font-size: 15px; font-weight: 500; margin: 0 0 10px; }
.fila { display: flex; flex-direction: column; gap: 8px; }
.item-fila { display: grid; grid-template-columns: auto 1fr auto; gap: 10px; align-items: center;
  background: #fff; border: 1px solid var(--border); border-radius: var(--raio); padding: 10px 12px; }
.item-fila .txt { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-2); font-size: 13px; }
.item-fila .txt strong { color: var(--text); font-weight: 500; }
.ponto { width: 10px; height: 10px; border-radius: 50%; flex: none; }
.ponto.baixa { background: var(--error); } .ponto.media { background: var(--colab-orange); }
.ponto.alta-c { background: var(--success); } .ponto.outra { background: var(--border); }

/* ===== 7. Visualizador / editor 50-50 ===== */
.migalha { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }
.migalha h2 { margin: 0; font-size: 17px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; }
.barra-doc { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 12px;
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--raio); padding: 8px 12px; }
.barra-doc select, .barra-doc input { background: #fff; color: var(--text);
  border: 1px solid var(--border); border-radius: 6px; padding: 6px 8px; font-size: 13px; font-family: inherit; }
.faixa { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 8px; margin-bottom: 12px; }
.faixa button { flex: none; padding: 4px; border-radius: var(--raio); background: #fff; }
.faixa button.ativa { border-color: var(--colab-orange); box-shadow: 0 0 0 2px #F9AB0066; }
.faixa img { display: block; height: 5.5rem; width: auto; border-radius: 4px; background: var(--surface); }
.faixa small { display: block; text-align: center; color: var(--text-2); font-size: 11px; }
.area-trab { display: grid; grid-template-columns: 1fr 1fr; gap: 0; align-items: start;
  border: 1px solid var(--border); border-radius: var(--raio); overflow: hidden; }
.pane-titulo { padding: 10px 16px; font-size: 12px; font-weight: 500; color: var(--text-2);
  border-bottom: 1px solid var(--border); background: var(--surface); }
.visor { background: var(--surface); overflow: auto; max-height: 78vh; border-right: 1px solid var(--border); }
.visor-dentro { position: relative; margin: 0 auto; }
.visor-dentro img { display: block; width: 100%; height: auto; background: #fff; }
.visor-dentro svg { position: absolute; inset: 0; width: 100%; height: 100%; }
.visor-dentro rect.caixa { fill: #F9AB0022; stroke: #B06000; stroke-width: 2; cursor: pointer; }
.visor-dentro rect.caixa:hover { fill: #F9AB0055; }
.visor-dentro rect.caixa.baixa-c { stroke: var(--error); fill: #D9302522; }
.visor-dentro rect.caixa.ok-c { stroke: #188038aa; }
.visor-dentro rect.caixa.sel { stroke: var(--colab-orange-dark); stroke-width: 4; fill: #F9AB0033; }
.painel-linha { background: #fff; padding: 14px; max-height: 78vh; overflow-y: auto; }
.abas { display: flex; gap: 8px; margin-bottom: 10px; }
.abas button.ativa { border-color: var(--colab-orange); background: var(--colab-orange-soft); font-weight: 500; }
.recorte { width: 100%; height: auto; border-radius: var(--raio); border: 1px solid var(--border); background: #fff; }
.meta-linha { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin: 10px 0; font-size: 13px; }
.conf { font-weight: 700; padding: 2px 10px; border-radius: 12px; font-size: 12px; }
.conf.baixa-c { background: #FCE8E6; color: var(--error); }
.conf.media-c { background: var(--colab-orange-soft); color: #B06000; }
.conf.alta-c { background: #E6F4EA; color: var(--success); }
details.camadas { margin: 8px 0; border: 1px solid var(--border); border-radius: var(--raio); }
details.camadas summary { cursor: pointer; padding: 8px 10px; color: var(--text-2); font-size: 13px; }
details.camadas pre { margin: 0; padding: 10px; white-space: pre-wrap; border-top: 1px solid var(--border);
  font-size: 13px; font-family: 'Roboto Mono', ui-monospace, Menlo, Consolas, monospace; }
textarea.diplo { width: 100%; min-height: 5rem; font-size: 13px; line-height: 1.7; resize: vertical;
  background: var(--mono-bg); color: var(--text); border: 1px solid var(--border);
  border-radius: var(--raio); padding: 10px; font-family: 'Roboto Mono', ui-monospace, Menlo, Consolas, monospace; }
textarea.diplo:focus { outline: 2px solid var(--colab-blue); }
.ocr-ref { background: var(--mono-bg); border: 1px solid var(--border); border-radius: var(--raio);
  padding: 12px 14px; font-family: 'Roboto Mono', ui-monospace, Menlo, Consolas, monospace;
  font-size: 13px; line-height: 1.8; }
.ocr-ref mark { background: var(--warn-soft); border-bottom: 2px dashed var(--colab-orange); padding: 0 1px; }
.botoes { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0; }
.dica { font-size: 12px; color: var(--text-2); }
.sugestao { border-left: 3px solid #9334E6; background: var(--surface); padding: 8px 10px;
  border-radius: 0 var(--raio) var(--raio) 0; margin: 8px 0; font-size: 13px; }
.sugestao small { color: var(--text-2); }
.hist { list-style: none; margin: 8px 0; padding: 0; font-size: 13px; }
.hist li { border-left: 2px solid var(--border); padding: 4px 0 4px 10px; margin-bottom: 6px; color: var(--text-2); }
.hist li strong { color: var(--text); }
.lista-linhas { display: flex; flex-direction: column; gap: 6px; max-height: 60vh; overflow-y: auto; }
.row-linha { display: grid; grid-template-columns: auto 1fr auto; gap: 10px; align-items: center; width: 100%;
  text-align: left; background: #fff; }
.row-linha.sel { border-color: var(--colab-orange); background: var(--colab-orange-soft); }
.row-linha .txt { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; color: var(--text-2); }

/* ===== Toasts (canto inferior esquerdo) ===== */
#toasts { position: fixed; left: 20px; bottom: 20px; display: flex; flex-direction: column; gap: 10px; z-index: 50; }
.toast { background: #202124; color: #fff; border-radius: var(--raio); border-left: 4px solid var(--colab-orange);
  padding: 12px 18px; max-width: 22rem; font-size: 13px; box-shadow: 0 2px 8px rgba(0,0,0,.3); }
.toast.erro { border-left-color: var(--error); }
.vazio { color: var(--text-2); padding: 24px; text-align: center; border: 1px dashed var(--border);
  border-radius: var(--raio); font-size: 13px; }
kbd { background: var(--surface); border: 1px solid var(--border); border-radius: 4px; padding: 0 6px; font-size: 12px; }

/* ===== 8. Rodapé ===== */
footer { background: var(--surface); border-top: 1px solid var(--border); margin-top: 28px; padding: 16px 0; }
footer .container { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap;
  font-size: 12px; color: var(--text-2); }
footer a { color: var(--colab-blue); text-decoration: none; margin-right: 18px; }
footer a:hover { text-decoration: underline; }

@media (max-width: 900px) {
  .corpo { grid-template-columns: 1fr; }
  .lateral { position: static; max-height: 16rem; }
  .principal { padding: 16px 0 0; }
  .area-trab { grid-template-columns: 1fr; }
  .visor { border-right: none; border-bottom: 1px solid var(--border); max-height: none; }
  .painel-linha { max-height: none; }
  .table-wrap table.docs { display: none; }
  .cards-mobile { display: grid; gap: 12px; padding: 16px; }
  .doc-card { border: 1px solid var(--border); border-radius: var(--raio); padding: 14px;
    display: flex; gap: 12px; align-items: flex-start; }
  .doc-card .meta { flex: 1; min-width: 0; }
  .doc-card .meta b { display: block; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .doc-card .meta span { font-size: 12px; color: var(--text-2); }
  .topo input[type=search] { display: none; }
  .step-line { width: 28px; }
}
 @media (max-width: 700px) {
   .container { padding-left: 12px; padding-right: 12px; }
   .topo .container:first-child { height: auto; min-height: 64px; padding-top: 8px; padding-bottom: 8px; flex-wrap: wrap; gap: 8px; }
   .marca { flex: 1 1 auto; min-width: 12rem; }
   .tabs { order: 5; flex-basis: 100%; height: 38px; }
   .tabs button { flex: 1; padding: 0 8px; }
   .topo input[type=search] { display: block; order: 3; flex: 1 1 12rem; min-width: 8rem; width: auto; }
   .topo select { order: 4; flex: 1 1 10rem; max-width: none; }
   .llm-pill, .quota { display: none; }
   .toolbar { position: sticky; top: 0; z-index: 19; }
   .toolbar .container { flex-wrap: nowrap; overflow-x: auto; scrollbar-width: thin; }
   .tool-btn { white-space: nowrap; flex: 0 0 auto; }
   .stepper { justify-content: flex-start; gap: 4px; padding-top: 16px; overflow-x: auto; flex-wrap: nowrap; }
   .step { white-space: nowrap; }
   .step-line { flex: 0 0 22px; margin: 0 4px; }
   .card { margin: 12px 0; }
   .card-body { padding: 14px; }
   .formats { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
   .fmt { padding: 10px; min-width: 0; }
   .fmt.selected { padding: 9px; }
   .engine-head { align-items: flex-start; }
   .engine-actions { width: 100%; }
   .engine-actions button { flex: 1; }
   .visual-quick { align-items: stretch; flex-direction: column; margin-left: 12px; margin-right: 12px; }
   .visual-quick-actions { width: 100%; }
   .visual-quick-actions button { flex: 1; }
   .principal { padding-left: 0; }
   .faixa img { height: 4.5rem; }
   .area-trab { margin-left: -1px; margin-right: -1px; }
   .visor, .painel-linha { max-height: 60vh; }
   .barra-doc { position: sticky; top: 42px; z-index: 10; }
   .barra-doc label { display: inline-flex; align-items: center; gap: 4px; }
   .cartoes { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
   .cartao { padding: 10px; }
   .cartao strong { font-size: 22px; }
   .job-log { max-height: 6rem; }
 }
 @media (max-width: 420px) {
   body { font-size: 13px; }
   .marca { min-width: 0; font-size: 16px; }
   .marca small { font-size: 10px; }
   .dropzone { padding: 28px 12px; }
   .dropzone h2 { font-size: 16px; }
   .linha-envio { align-items: stretch !important; flex-direction: column; margin-left: 12px !important; margin-right: 12px !important; }
   .linha-envio .toggle, .linha-envio select, .linha-envio button { width: 100%; }
   .formats { grid-template-columns: 1fr; }
   .engine-meta span { max-width: 100%; overflow-wrap: anywhere; }
   .botoes button { flex: 1 1 100%; }
 }
</style>
</head>
<body>
<!-- 1. Barra superior -->
<header class="topo">
  <div class="container">
    <div class="marca"><span class="logo-mark" aria-hidden="true">⌗</span><span>OCR STUDIO V1<small>ocr-historico-br · revisão local</small></span></div>
    <nav class="tabs" aria-label="Navegação principal">
      <button id="tabConverter" class="active" type="button">Converter</button>
      <button id="tabDocs" type="button">Meus documentos</button>
    </nav>
    <input id="busca" type="search" placeholder="Buscar documento…" aria-label="Buscar documento">
    <select id="filtro-doc" aria-label="Filtrar documentos por status">
      <option value="">Todos os documentos</option>
      <option value="aguardando_ocr">aguardando_ocr</option>
      <option value="concluido">concluído</option>
      <option value="parcial">parcial</option>
      <option value="erro">erro</option>
    </select>
    <span id="llm-pill" class="pilula llm-off">LLM…</span>
    <span class="quota" id="quota" title="Documentos no banco local">banco local</span>
  </div>
  <div class="container" style="padding-bottom:8px"><div class="mini-stats" id="mini-stats"></div></div>
</header>

<!-- 2. Barra de ferramentas estilo Colab -->
<div class="toolbar">
  <div class="container" role="toolbar" aria-label="Ações de documentos">
    <button class="tool-btn" id="btnUpload" type="button">＋ Enviar arquivos</button>
    <button class="tool-btn" id="btnRepro" type="button">⟳ Reprocessar</button>
    <button class="tool-btn" id="btnDlAll" type="button">⬇ Baixar tudo</button>
  </div>
</div>
<div class="progress-track idle" id="progressTrack" aria-hidden="true"><div class="progress-bar"></div></div>

<div class="container">
  <!-- 3. Stepper do fluxo -->
  <div class="stepper" aria-label="Etapas do fluxo">
    <div class="step" id="st1"><span class="num" aria-hidden="true">1</span> Enviar</div>
    <div class="step-line" aria-hidden="true"></div>
    <div class="step active" id="st2"><span class="num" aria-hidden="true">2</span> Configurar</div>
    <div class="step-line" aria-hidden="true"></div>
    <div class="step" id="st3"><span class="num" aria-hidden="true">3</span> Converter e baixar</div>
  </div>

  <!-- 4. Zona de upload: label+input visível ao AT (sem hidden — abre o seletor em todos os navegadores) -->
  <section class="card" aria-label="Envio de arquivos">
    <input type="file" id="fileInput" class="sr-only" multiple accept=".pdf,.jpg,.jpeg,.png,.tiff,.tif,application/pdf,image/*">
    <label class="dropzone" id="dropzone" for="fileInput">
      <svg width="52" height="52" viewBox="0 0 24 24" fill="none" stroke="#F9AB00" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M16 16l-4-4-4 4"/><path d="M12 12v9"/>
        <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/>
      </svg>
      <h2>Arraste PDFs ou imagens aqui</h2>
      <p id="dropHint">PDF, JPG, PNG, TIFF — clique para selecionar ou solte os arquivos</p>
      <span class="btn-primary" id="btnPick">Selecionar arquivos</span>
    </label>
    <div class="linha-envio" style="display:flex;gap:12px;justify-content:center;align-items:center;flex-wrap:wrap;margin:12px 16px">
      <label class="toggle"><input type="checkbox" id="chkProcessar" checked> Executar OCR após enviar</label>
      <label class="toggle">Motor
        <select id="selMotor" aria-label="Motor de OCR">
          <option value="auto">automático (melhor disponível)</option>
        </select>
      </label>
      <button class="btn-outline" id="btnEnviar" type="button">Enviar e reconhecer</button>
    </div>
    <div class="visual-quick" id="visualQuick" aria-live="polite">
       <div><strong>Modelos visuais locais</strong><span id="visualQuickStatus">Processam a página inteira (sem caixas por linha) — escolha um abaixo.</span></div>
       <div class="visual-quick-actions">
         <div class="chips" id="visualChips" role="group" aria-label="Escolher motor visual"></div>
          <label class="toggle" title="RX 580 via Vulkan; desmarque para CPU est\u00e1vel"><input type="checkbox" id="chkGpu"> placa de v\u00eddeo</label>
       </div>
     </div>
     <ul class="file-list" id="dropLista" aria-live="polite"></ul>
    <div class="job" id="painelJob" hidden>
      <div class="job-head">
        <strong id="jobMsg">Aguardando…</strong>
        <span><span id="jobPct">0%</span> · <button id="btnCancelar" type="button">Cancelar</button></span>
      </div>
      <div class="job-bar" aria-hidden="true"><i id="jobBar"></i></div>
      <div class="job-log" id="jobLog"></div>
    </div>
  </section>

  <!-- 5. Configuração (etapa 2 — preferência local; o lote usa YAML + --perfil) -->
  <section class="card" aria-label="Configuração de conversão">
    <div class="card-head">Configuração de conversão <span class="dica">preferência local — o lote usa o YAML e <kbd>--perfil</kbd></span></div>
    <div class="card-body">
      <div class="section-label" id="lblLang">Idiomas do documento</div>
      <div class="chips" role="group" aria-labelledby="lblLang" id="langChips">
        <span class="chip" role="checkbox" aria-checked="false" tabindex="0">Automático</span>
        <span class="chip selected" role="checkbox" aria-checked="true" tabindex="0">Português</span>
        <span class="chip" role="checkbox" aria-checked="false" tabindex="0">English</span>
        <span class="chip" role="checkbox" aria-checked="false" tabindex="0">Español</span>
        <span class="chip" role="checkbox" aria-checked="false" tabindex="0">Français</span>
        <span class="chip" role="checkbox" aria-checked="false" tabindex="0">Alemão</span>
      </div>
      <div class="section-label" id="lblFmt">Formato de saída</div>
      <div class="formats" role="radiogroup" aria-labelledby="lblFmt" id="fmtGrid">
        <div class="fmt selected" role="radio" aria-checked="true" tabindex="0"><span class="fmt-badge b-docx">W</span><div>DOCX<small>via exportação</small></div></div>
        <div class="fmt" role="radio" aria-checked="false" tabindex="0"><span class="fmt-badge b-pdf">PDF</span><div>PDF pesquisável<small>OCRmyPDF / fallback</small></div></div>
        <div class="fmt" role="radio" aria-checked="false" tabindex="0"><span class="fmt-badge b-txt">TXT</span><div>TXT<small>bruto + diplomático</small></div></div>
        <div class="fmt" role="radio" aria-checked="false" tabindex="0"><span class="fmt-badge b-xlsx">X</span><div>TSV<small>troca com planilha</small></div></div>
        <div class="fmt" role="radio" aria-checked="false" tabindex="0"><span class="fmt-badge b-epub">EP</span><div>Markdown<small>leitura</small></div></div>
        <div class="fmt" role="radio" aria-checked="false" tabindex="0"><span class="fmt-badge b-fb2">FB</span><div>JSON<small>auditoria</small></div></div>
      </div>
      <div class="section-label">Opções de reconhecimento</div>
      <div class="toggles" id="ocrToggles">
        <label class="toggle"><input type="checkbox" data-opt="deskew"> Corrigir inclinação (deskew)</label>
        <label class="toggle"><input type="checkbox" data-opt="denoise"> Remover ruído</label>
        <label class="toggle"><input type="checkbox" data-opt="clahe"> CLAHE / contraste</label>
        <label class="toggle"><input type="checkbox" data-opt="tesseract"> Forçar Tesseract (--engine)</label>
        <label class="toggle"><input type="checkbox" data-opt="kraken"> Linha manuscrita (Kraken)</label>
       <div class="engine-panel" id="enginePanel" aria-live="polite">
         <div class="engine-head">
           <div><strong id="engineNome">Motor automático</strong><span id="engineEstado" class="pilula engine-status">verificando…</span></div>
           <div class="engine-actions"><button class="btn-outline" id="btnAtualizarMotores" type="button">↻ Atualizar motores</button>
           <button class="btn-outline" id="btnPaddleVL" type="button" hidden>Iniciar servidor visual</button></div>
         </div>
         <p id="engineDescricao">Consultando os motores disponíveis neste computador…</p>
         <div class="engine-meta" id="engineMeta"></div>
       </div>
      </div>
    </div>
  </section>

  <div class="corpo">
    <aside class="lateral" aria-label="Documentos">
      <h2>Documentos</h2>
      <div id="lista-docs"><p class="vazio">carregando…</p></div>
    </aside>
    <main class="principal">
      <section id="view-painel">
        <div class="cartoes" id="cartoes"></div>
        <div class="secao"><h2>Distribuição por status</h2><div class="barra-dist" id="dist"></div><div id="dist-leg"></div></div>
        <!-- 6. Fila de documentos (tabela estilo ABBYY, dados reais) -->
        <div class="card" id="cardDocs">
          <div class="card-head">Fila de documentos <button class="btn-primary" style="padding:8px 18px" id="btnConvert" type="button">Converter tudo</button></div>
          <div class="table-wrap">
            <table class="docs" aria-label="Documentos registrados">
              <thead><tr><th scope="col"></th><th scope="col">Nome</th><th scope="col">Páginas</th><th scope="col">Tipo</th><th scope="col">Status</th><th scope="col">Ações</th></tr></thead>
              <tbody id="tabela-docs"><tr><td colspan="6" class="vazio">carregando…</td></tr></tbody>
            </table>
          </div>
          <div class="cards-mobile" id="cardsMobile"></div>
        </div>
        <div class="secao"><h2>Fila prioritária — todas as coleções</h2><div class="fila" id="fila-global"></div></div>
        <p class="dica">Atalhos na área do documento: <kbd>↑</kbd><kbd>↓</kbd> linhas · <kbd>←</kbd><kbd>→</kbd> páginas · <kbd>Ctrl+Enter</kbd> salvar · <kbd>1</kbd> revisada · <kbd>2</kbd> ilegível · <kbd>3</kbd> treinamento.</p>
      </section>
      <section id="view-doc" hidden>
        <div class="migalha">
          <button id="btn-voltar" type="button">← Documentos</button>
          <h2 id="doc-nome"></h2>
          <span id="doc-pills"></span>
        </div>
        <p id="doc-erro" class="vazio" hidden></p>
        <div class="barra-doc">
          <label>Camada
            <select id="camada">
              <option value="overlay">overlay (caixas)</option>
              <option value="original">original</option>
              <option value="pre">pré-processada</option>
            </select>
          </label>
          <button id="zoom-menos" type="button">−</button>
          <span id="zoom-rotulo">100%</span>
          <button id="zoom-mais" type="button">+</button>
          <button id="zoom-ajustar" type="button">ajustar</button>
          <span style="flex:1"></span>
          <label>Coleção <input id="colecao" value="revisao_web" size="14"></label>
          <button id="btn-exportar" type="button">Exportar treinamento</button>
          <span id="exp-msg" class="dica"></span>
        </div>
        <div class="faixa" id="faixa"></div>
        <!-- 7. Visualizador / editor dividido 50/50 -->
        <div class="area-trab">
          <div>
            <div class="pane-titulo">Original digitalizado</div>
            <div class="visor" id="visor"><div class="visor-dentro" id="visor-dentro"></div></div>
          </div>
          <div>
            <div class="pane-titulo">Texto reconhecido (editável por linha)</div>
            <div class="painel-linha">
              <div class="abas">
                <button id="aba-linha" class="ativa" type="button">Linha</button>
                <button id="aba-fila" type="button">Fila do documento</button>
              </div>
              <div id="tab-linha"></div>
              <div id="tab-fila" hidden><div class="lista-linhas" id="fila-doc"></div></div>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>
</div>

<!-- 8. Rodapé -->
<footer>
  <div class="container">
    <span><a href="#" id="lnkAjuda">Ajuda</a><a href="/api/resumo">API</a><a href="#" id="lnkTermos">Termos</a></span>
    <span>OCR STUDIO V1 · ocr-historico-br — painel 100% local, sem nuvem</span>
  </div>
</footer>
<div id="toasts" aria-live="polite"></div>
<script>
const $ = (id) => document.getElementById(id);
const estado = { docs: [], doc: null, paginas: [], pagina: null, linhasPagina: [],
  linha: null, detalhe: null, camada: 'overlay', zoom: 1, filaDoc: [], motores: [], motorAviso: '', vl: null, vlOnlineAnterior: null };
const MOTOR_LABELS = {
  auto: 'Automático (melhor disponível)', qwen3_vl: 'Qwen3-VL 4B (visão de página)', glm_ocr: 'GLM-OCR (layout/tabelas)', deepseek_ocr2: 'DeepSeek-OCR-2 (documentos/markdown)', olmocr: 'olmOCR', paddleocr: 'PaddleOCR clássico',
  tesseract: 'Tesseract', kraken: 'Kraken (manuscrito)', easyocr: 'EasyOCR',
  pdf_texto: 'Texto nativo de PDF', surya: 'Surya', calamari: 'Calamari', ensemble: 'Ensemble'
};
/* Motores de visão (página inteira, sem caixas por linha): seleção rápida + grupos do seletor. */
const MOTORES_VISUAIS = ['qwen3_vl', 'glm_ocr', 'deepseek_ocr2', 'olmocr'];
function opcaoMotor(x) {
  return '<option value="' + x.nome + '"' + (x.disponivel ? '' : ' disabled') +
    (x.motivo ? ' title="' + esc(x.motivo) + '"' : '') +
    '>' + esc(MOTOR_LABELS[x.nome] || x.nome) + (x.disponivel ? ' ✓' : ' — ' + esc(x.motivo || 'indisponível')) + '</option>';
}
function desenharChipsVisuais() {
  const raiz = $('visualChips'); if (!raiz) return;
  const atual = (($('selMotor') || {}).value || '');
  raiz.innerHTML = MOTORES_VISUAIS.map((nome) => {
    const info = ((estado.motores || []).find((x) => x.nome === nome)) || {};
    const rotulo = MOTOR_LABELS[nome] || nome;
    const dica = rotulo + ' — ' + (info.disponivel ? 'disponível' : (info.motivo || 'indisponível'));
    return '<button type="button" class="chip' + (atual === nome ? ' selected' : '') + '" data-motor-visual="' + nome +
      '" title="' + esc(dica) + '" aria-pressed="' + (atual === nome) + '">' + esc(rotulo) + '</button>';
  }).join('');
  for (const b of raiz.querySelectorAll('[data-motor-visual]')) b.onclick = () => selecionarMotorVisual(b.dataset.motorVisual);
}
function esc(s) { return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
let requestsAtivas = 0;
function prog(on) {
  requestsAtivas = Math.max(0, requestsAtivas + (on ? 1 : -1));
  const t = $('progressTrack'); if (t) t.classList.toggle('idle', requestsAtivas === 0);
}
async function api(caminho, opcoes) {
  prog(true);
  try {
    const r = await fetch(caminho, opcoes);
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.erro || ('HTTP ' + r.status));
    return j;
  } finally { prog(false); }
}
function toast(msg, erro) {
  const d = document.createElement('div');
  d.className = 'toast' + (erro ? ' erro' : '');
  d.textContent = msg;
  $('toasts').appendChild(d);
  setTimeout(() => d.remove(), 5200);
}
function confClasse(c) { return c == null ? 'baixa-c' : (c < 0.7 ? 'baixa-c' : (c < 0.85 ? 'media-c' : 'alta-c')); }
function confTxt(c) { return c == null ? 'sem conf.' : Math.round(c * 100) + '%'; }
function pillStatus(s) {
  if (s === 'concluido') return 'Concluído';
  if (s === 'erro') return 'Erro';
  if (s === 'parcial') return 'Processando';
  return 'Na fila';
}
function pillClasse(s) {
  if (s === 'concluido') return 'st-concluido';
  if (s === 'erro') return 'st-erro';
  if (s === 'parcial') return 'st-parcial';
  return 'st-aguardando_ocr';
}
/* ---------- painel ---------- */
let pollTimer = null;
async function boot() {
  try {
    const llm = await api('/api/llm-estado');
    const pill = $('llm-pill');
    pill.textContent = llm.enabled ? ('LLM · ' + llm.model) : 'LLM desativado';
    pill.className = 'pilula ' + (llm.enabled ? 'llm-ok' : 'llm-off');
  } catch (e) { $('llm-pill').textContent = 'LLM?'; }
  await Promise.all([carregarDocs(), carregarPainel(), carregarMotores(), carregarPaddleStatus(true), sondarTrabalho()]);
  restaurarPrefs();
  setInterval(() => carregarPaddleStatus(true), 3500);
}
function motorAtual() {
  const nome = ($('selMotor') || {}).value || 'auto';
  return estado.motores.find((x) => x.nome === nome) || { nome, disponivel: true };
}
function desenharMotorAtual() {
  const item = motorAtual();
  const nome = item.nome || 'auto';
  const visual = ['qwen3_vl', 'glm_ocr', 'deepseek_ocr2', 'olmocr'].includes(nome);
  const carregando = visual && !!(estado.vl && estado.vl.carregando);
  const disponivel = nome === 'auto' || item.disponivel !== false || carregando;
  const painel = $('enginePanel');
  const estadoMotor = $('engineEstado');
  if (painel) painel.classList.toggle('indisponivel', !disponivel && !carregando);
  if ($('engineNome')) $('engineNome').textContent = MOTOR_LABELS[nome] || nome;
  if (estadoMotor) {
    estadoMotor.textContent = carregando ? 'carregando modelo…' : (disponivel ? 'disponível' : 'indisponível');
    estadoMotor.className = 'pilula engine-status ' + (carregando ? '' : (disponivel ? 'llm-ok' : 'llm-off'));
  }
  let descricao = item.descricao || 'Motor local configurado para este lote.';
  if (!disponivel && item.motivo) descricao += ' Motivo: ' + item.motivo + '.';
  if (['qwen3_vl', 'glm_ocr', 'deepseek_ocr2', 'olmocr'].includes(nome)) {
    descricao += disponivel
      ? ' As páginas serão enviadas ao servidor visual local e voltarão como um bloco para revisão visual.'
      : ' Inicie o servidor visual local pelo botão abaixo.';
    if (nome === 'olmocr') descricao += ' O olmOCR prioriza ordem natural de leitura e Markdown.';
    if (estado.vl && estado.vl.mensagem) descricao += ' ' + estado.vl.mensagem;
  }
  if ($('engineDescricao')) $('engineDescricao').textContent = descricao;
  const meta = [];
  if (item.endpoint) meta.push('<span>endpoint: ' + esc(item.endpoint) + '</span>');
  if (item.modelo) meta.push('<span>modelo: ' + esc(item.modelo) + '</span>');
  if (['qwen3_vl','glm_ocr','deepseek_ocr2'].includes(nome)) meta.push('<span>sem nuvem · CPU/GPU local</span>');
  if ($('engineMeta')) $('engineMeta').innerHTML = meta.join('');
}
async function carregarMotores(silencioso) {
  try {
    const m = await api('/api/motores');
    estado.motores = m.motores || [];
    const sel = $('selMotor');
    if (!sel) return;
    const atual = sel.value || 'auto';
    const visuais = estado.motores.filter((x) => MOTORES_VISUAIS.includes(x.nome));
    const outros = estado.motores.filter((x) => !MOTORES_VISUAIS.includes(x.nome));
    sel.innerHTML = '<option value="auto">' + MOTOR_LABELS.auto + '</option>' +
      '<optgroup label="Visão — página inteira (revisão obrigatória)">' + visuais.map(opcaoMotor).join('') + '</optgroup>' +
      '<optgroup label="Clássicos, HTR e texto nativo">' + outros.map(opcaoMotor).join('') + '</optgroup>';
    const opcaoAtual = Array.from(sel.options).find((x) => x.value === atual && !x.disabled);
    const preservaVisual = ['qwen3_vl', 'glm_ocr', 'deepseek_ocr2', 'olmocr'].includes(atual) && estado.vl && estado.vl.carregando;
    if (atual !== 'auto' && (opcaoAtual || preservaVisual)) sel.value = atual;
    else if (atual === 'auto' || !sel.value) sel.value = 'auto';
    desenharMotorAtual();
    desenharChipsVisuais();
    if (m.aviso && (!silencioso || estado.motorAviso !== m.aviso)) {
      estado.motorAviso = m.aviso; toast(m.aviso, true);
    }
  } catch (e) {
    if (!silencioso) toast('Não foi possível atualizar os motores: ' + e.message, true);
  }
}
function motorVisualSelecionado() {
  const motor = (($('selMotor') || {}).value || 'qwen3_vl');
  if (motor === 'glm_ocr') return 'glm_ocr';
  if (motor === 'deepseek_ocr2') return 'deepseek_ocr2';
  if (motor === 'olmocr') return 'olmocr';
  return 'qwen3_vl';
}
function nomeMotorVisual(motor) { if (motor === 'glm_ocr') return 'GLM-OCR'; if (motor === 'deepseek_ocr2') return 'DeepSeek-OCR-2'; if (motor === 'olmocr') return 'olmOCR'; return 'Qwen3-VL 4B'; }
function desenharPaddleStatus(s) {
  estado.vl = s;
  const btn = $('btnPaddleVL');
  if (!btn) return;
  const motor = motorVisualSelecionado();
  const selecionado = ['qwen3_vl', 'glm_ocr', 'deepseek_ocr2', 'olmocr'].includes(($('selMotor') || {}).value || '');
  btn.hidden = !selecionado;
  btn.disabled = !!s.iniciando;
  if (s.online) {
    btn.textContent = s.gerenciado ? 'Parar servidor visual' : 'Servidor visual externo';
    btn.disabled = !s.gerenciado;
    btn.title = s.gerenciado ? 'Parar o servidor iniciado pela GUI' : 'Servidor externo ativo; não será encerrado pela GUI';
  } else if (s.gerenciado) {
    btn.textContent = s.iniciando ? 'Carregando modelo…' : 'Parar servidor sem resposta';
    btn.disabled = false;
    btn.title = s.mensagem || '';
  } else {
    btn.textContent = 'Iniciar ' + nomeMotorVisual(motor);
    btn.title = s.pode_iniciar ? 'Iniciar o servidor visual local' : (s.mensagem || 'Servidor não pode ser iniciado aqui');
  }
  desenharMotorAtual();
  desenharChipsVisuais();
  const resumo = $('visualQuickStatus');
  if (resumo) resumo.textContent = nomeMotorVisual(motor) + ': ' + (s.mensagem || 'estado desconhecido') + (s.modelo ? ' · ' + s.modelo : '');
}
async function carregarPaddleStatus(silencioso) {
  const motor = motorVisualSelecionado();
  try {
    const s = await api('/api/paddle-vl?motor=' + encodeURIComponent(motor));
    const mudou = estado.vlOnlineAnterior !== null && estado.vlOnlineAnterior !== !!s.online;
    estado.vlOnlineAnterior = !!s.online;
    desenharPaddleStatus(s);
    $('btnAtualizarMotores').disabled = !!s.iniciando;
    if (mudou || (s.online && !estado.motores.length)) await carregarMotores(true);
    if (mudou) {
      toast(s.online ? 'Servidor visual ' + nomeMotorVisual(motor) + ' ficou disponível.' :
        (s.gerenciado ? 'Servidor visual ' + nomeMotorVisual(motor) + ' foi encerrado.' : 'Servidor visual ficou offline.'));
      await carregarDocs();
    }
  } catch (e) {
    if (!silencioso) toast('Não foi possível consultar o servidor ' + nomeMotorVisual(motor) + ': ' + e.message, true);
  }
}
async function alternarPaddleVL() {
  const motor = motorVisualSelecionado();
  const s = estado.vl || {};
  const rota = s.online ? '/api/paddle-vl/parar' : '/api/paddle-vl/iniciar';
  const btn = $('btnPaddleVL');
  if (btn) btn.disabled = true;
  try {
    const gpu = !!($('chkGpu') && $('chkGpu').checked);
    const novo = await api(rota, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ motor: motor, gpu: gpu }) });
    desenharPaddleStatus(novo);
    await carregarMotores(true);
    toast(novo.iniciando ? 'Servidor ' + nomeMotorVisual(motor) + (gpu?' (placa)':' (CPU)') + ' iniciado; carregando o modelo…' : (novo.online ? nomeMotorVisual(motor) + ' pronto.' : 'Servidor visual parado.'));
    if (novo.iniciando) setTimeout(() => carregarPaddleStatus(true), 1800);
  } catch (e) {
    toast('Falha ao alternar ' + nomeMotorVisual(motor) + ': ' + e.message, true);
    if (btn) btn.disabled = false;
  }
}
function desenharTrabalho(t) {
  const painel = $('painelJob');
  if (!painel) return;
  painel.hidden = !(t.estado !== 'ocioso' || (t.log || []).length);
  $('jobMsg').textContent = t.mensagem || '';
  $('jobPct').textContent = (t.percentual || 0) + '%';
  $('jobBar').style.width = (t.percentual || 0) + '%';
  const log = $('jobLog');
  log.innerHTML = (t.log || []).slice(-30).map((l) => '<div>' + esc(l) + '</div>').join('');
  log.scrollTop = log.scrollHeight;
  const rodando = t.estado === 'rodando';
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  if (rodando) pollTimer = setInterval(sondarTrabalho, 800);
}
function iniciarSondagem() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  estado.jobNotificado = null;
  pollTimer = setInterval(sondarTrabalho, 800);
}
async function sondarTrabalho() {
  try {
    const t = await api('/api/trabalho');
    desenharTrabalho(t);
    if (['concluido', 'erro', 'cancelado'].includes(t.estado)) {
      await Promise.all([carregarDocs(), carregarPainel()]);
      // notifica uma única vez por trabalho (evita repetir o toast a cada ciclo)
      const assinatura = t.estado + '|' + (t.mensagem || '');
      if (estado.jobNotificado !== assinatura) {
        estado.jobNotificado = assinatura;
        if (t.estado === 'concluido') {
          const r = t.resumo || {};
          toast('OCR concluído: ' + (r.documentos || 0) + ' doc(s), ' + (r.paginas_ok || 0) + ' pág. ok, ' + (r.paginas_erro || 0) + ' com erro.');
        } else if (t.estado === 'erro') toast(t.mensagem || 'Falha no OCR.', true);
      }
    }
  } catch (e) { /* próxima sondagem tenta de novo */ }
}
async function enfileirarOcr(ids, forcar) {
  const motor = ($('selMotor') || {}).value || 'auto';
  const corpo = { engine: motor, forcar: !!forcar, retry_failed: true };
  if (ids && ids.length) corpo.ids = ids;
  try {
    const j = await api('/api/processar', { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo) });
    desenharTrabalho(j.trabalho);
    iniciarSondagem();
    toast('OCR iniciado (' + (motor || 'auto') + '). Acompanhe o progresso abaixo.');
  } catch (e) {
    if (/409|andamento/.test(e.message)) toast('Já há um OCR em andamento — aguarde ou cancele.', true);
    else toast('Falha ao iniciar OCR: ' + e.message, true);
  }
}
async function baixarProdutos(id) {
  try {
    const j = await api('/api/produtos?id=' + encodeURIComponent(id));
    if (!j.arquivos.length) { toast('Sem produtos exportados ainda — reconheça primeiro.', true); return; }
    for (const a of j.arquivos) {
      const link = document.createElement('a');
      link.href = '/api/download?id=' + encodeURIComponent(id) + '&arquivo=' + encodeURIComponent(a.nome);
      link.download = a.nome;
      document.body.appendChild(link); link.click(); link.remove();
      await new Promise((r) => setTimeout(r, 300));
    }
    toast(j.arquivos.length + ' produto(s) baixado(s).');
  } catch (e) { toast('Falha ao baixar: ' + e.message, true); }
}
let docsRequestSeq = 0;
async function carregarDocs() {
  const requestSeq = ++docsRequestSeq;
  const params = new URLSearchParams();
  if ($('busca').value) params.set('busca', $('busca').value);
  if ($('filtro-doc').value) params.set('status', $('filtro-doc').value);
  const dados = await api('/api/documentos?' + params.toString());
  if (requestSeq !== docsRequestSeq) return;
  estado.docs = dados.documentos;
  $('lista-docs').innerHTML = dados.documentos.map((d) =>
    '<button class="doc' + (estado.doc && estado.doc.id === d.id ? ' ativo' : '') + '" data-doc="' + d.id + '">' +
    '<span class="nome">' + esc(d.nome) + '</span>' +
    '<span class="meta"><span class="st st-' + d.status + '">' + d.status + '</span><span>' +
    d.tipo + ' · ' + d.paginas + ' pág.</span></span></button>').join('') ||
    '<p class="vazio">Nenhum documento neste filtro.</p>';
  for (const b of document.querySelectorAll('#lista-docs [data-doc]'))
    b.onclick = () => abrirDoc(b.dataset.doc);
  desenharTabelaDocs();
}
function desenharTabelaDocs() {
  const tb = $('tabela-docs');
  if (!tb) return;
  if (!estado.docs.length) {
    tb.innerHTML = '<tr><td colspan="6"><div class="vazio">Nenhum documento ainda — envie arquivos e rode <kbd>ocrhist processar</kbd>.</div></td></tr>';
    $('cardsMobile').innerHTML = '';
    return;
  }
  tb.innerHTML = estado.docs.map((d) =>
    '<tr><td><span class="thumb">' + esc(String(d.tipo || '?').slice(0, 4).toUpperCase()) + '</span></td>' +
    '<td>' + esc(d.nome) + '</td><td>' + d.paginas + '</td><td>' + esc(d.tipo) + '</td>' +
    '<td><span class="st ' + pillClasse(d.status) + '">' + pillStatus(d.status) + '</span></td>' +
    '<td><div class="row-actions"><button class="icon-btn" data-ver-doc="' + d.id + '" title="Revisar" aria-label="Revisar ' + esc(d.nome) + '">👁</button>' +
    '<button class="icon-btn" data-ocr-doc="' + d.id + '" title="Reconhecer / reprocessar" aria-label="OCR ' + esc(d.nome) + '">⟳</button>' +
    '<button class="icon-btn" data-exp-doc="' + d.id + '" title="Baixar produtos" aria-label="Baixar ' + esc(d.nome) + '">⬇</button></div></td></tr>'
  ).join('');
  $('cardsMobile').innerHTML = estado.docs.map((d) =>
    '<div class="doc-card"><span class="thumb">' + esc(String(d.tipo || '?').slice(0, 4).toUpperCase()) + '</span>' +
    '<div class="meta"><b>' + esc(d.nome) + '</b><span>' + esc(d.tipo) + ' · ' + d.paginas + ' pág.</span>' +
    '<div style="margin-top:6px"><span class="st ' + pillClasse(d.status) + '">' + pillStatus(d.status) + '</span></div></div>' +
    '<button class="icon-btn" data-ver-doc="' + d.id + '" aria-label="Visualizar ' + esc(d.nome) + '">👁</button></div>'
  ).join('');
  for (const b of document.querySelectorAll('[data-ver-doc]'))
    b.onclick = () => abrirDoc(b.dataset.verDoc);
  for (const b of document.querySelectorAll('[data-ocr-doc]'))
    b.onclick = () => enfileirarOcr([b.dataset.ocrDoc], true);
  for (const b of document.querySelectorAll('[data-exp-doc]'))
    b.onclick = () => baixarProdutos(b.dataset.expDoc);
}
function atualizaStepper(total, fila) {
  const s1 = $('st1'), s2 = $('st2'), s3 = $('st3');
  s1.className = 'step ' + (total > 0 ? 'done' : 'active');
  s1.querySelector('.num').textContent = total > 0 ? '✓' : '1';
  s2.className = 'step active';
  s3.className = 'step ' + (total > 0 && fila === 0 ? 'done' : '');
  s3.querySelector('.num').textContent = (total > 0 && fila === 0) ? '✓' : '3';
}
async function carregarPainel() {
  const r = await api('/api/resumo');
  $('mini-stats').innerHTML = '<span><strong>' + r.documentos.total + '</strong> docs</span>' +
    '<span><strong>' + r.linhas.fila + '</strong> na fila</span>';
  $('quota').textContent = r.documentos.total + ' documento(s) no banco';
  $('cartoes').innerHTML =
    cartao(r.documentos.total, 'documentos') +
    cartao(r.linhas.fila, 'linhas na fila') +
    cartao(r.linhas.baixa_confianca, 'baixa confiança') +
    cartao(r.linhas.revisadas, 'revisadas') +
    cartao(r.correcoes, 'correções auditadas');
  const cores = { concluido: '#188038', parcial: '#F9AB00', erro: '#D93025', aguardando_ocr: '#DADCE0' };
  const tot = r.documentos.total || 1;
  let barras = '', leg = [];
  for (const [k, v] of Object.entries(r.documentos.por_status)) {
    barras += '<i style="width:' + Math.round(v / tot * 100) + '%;background:' + (cores[k] || '#5F6368') + '"></i>';
    leg.push('<span class="pilula">' + esc(k) + ' · ' + v + '</span>');
  }
  $('dist').innerHTML = barras;
  $('dist-leg').innerHTML = leg.join(' ');
  atualizaStepper(r.documentos.total, r.linhas.fila);
  const fila = await api('/api/revisao?limite=15');
  $('fila-global').innerHTML = fila.linhas.map((l) => itemFilaHtml(l, true)).join('') ||
    '<p class="vazio">Fila vazia — nada exigindo revisão. Bom trabalho de arquivo!</p>';
  ligarFila($('fila-global'));
}
function cartao(n, rotulo) { return '<div class="cartao"><strong>' + n + '</strong><span>' + rotulo + '</span></div>'; }
function itemFilaHtml(l, comDoc) {
  const cls = l.confianca == null || l.confianca < 0.7 ? 'baixa' : (l.confianca < 0.85 ? 'media' : 'alta-c');
  return '<div class="item-fila"><span class="ponto ' + cls + '"></span>' +
    '<span class="txt"><strong>' + esc(comDoc ? l.documento + ' · p.' + l.pagina + ' · l.' + l.numero : ('l.' + l.numero)) +
    '</strong> ' + esc((l.texto || '').slice(0, 90)) + ' <span class="st st-' + l.status + '">' + l.status + ' · ' + confTxt(l.confianca) + '</span></span>' +
    '<button type="button" data-abrir-doc="' + l.documento_id + '" data-pagina="' + l.pagina + '" data-linha="' + l.id + '">Abrir</button></div>';
}
function ligarFila(raiz) {
  for (const b of raiz.querySelectorAll('[data-abrir-doc]'))
    b.onclick = () => abrirDoc(b.dataset.abrirDoc, { pagina: Number(b.dataset.pagina), linha: b.dataset.linha });
}
/* ---------- documento ---------- */
async function abrirDoc(id, salto) {
  const d = await api('/api/documento?id=' + encodeURIComponent(id));
  estado.doc = d; estado.pagina = null; estado.linha = null; estado.zoom = 1;
  $('view-painel').hidden = true; $('view-doc').hidden = false;
  $('tabConverter').classList.remove('active'); $('tabDocs').classList.add('active');
  $('doc-nome').textContent = d.nome;
  $('doc-pills').innerHTML = '<span class="st st-' + d.status + '">' + d.status + '</span>' +
    '<span class="pilula">' + esc(d.tipo) + '</span>' +
    '<span class="pilula">SHA ' + esc((d.sha256 || '').slice(0, 12)) + '…</span>';
  const boxErro = $('doc-erro');
  if (d.erro) { boxErro.hidden = false; boxErro.textContent = 'Erro: ' + d.erro; } else boxErro.hidden = true;
  estado.paginas = d.paginas;
  $('faixa').innerHTML = d.paginas.map((p) =>
    '<button type="button" data-pag="' + p.id + '" title="página ' + p.numero + '">' +
    '<img loading="lazy" src="/api/pagina/imagem?id=' + p.id + '&tipo=overlay" alt="pág. ' + p.numero + '">' +
    '<small>' + p.numero + ' · ' + p.status + '</small></button>').join('');
  for (const b of document.querySelectorAll('#faixa [data-pag]'))
    b.onclick = () => carregarPagina(b.dataset.pag);
  await carregarDocs();
  const fila = await api('/api/revisao?documento=' + encodeURIComponent(id) + '&limite=200');
  estado.filaDoc = fila.linhas;
  $('fila-doc').innerHTML = fila.linhas.map((l) => itemFilaHtml(l, false)).join('') || '<p class="vazio">Sem fila neste documento.</p>';
  ligarFila($('fila-doc'));
  let alvo = null;
  if (salto && salto.pagina) alvo = d.paginas.find((p) => p.numero === salto.pagina) || d.paginas[0];
  else alvo = d.paginas[0];
  if (alvo) await carregarPagina(alvo.id, salto && salto.linha);
  else { $('visor-dentro').innerHTML = '<p class="vazio">Documento sem páginas.</p>'; $('tab-linha').innerHTML = ''; }
}
async function carregarPagina(pid, linhaAlvo) {
  const p = await api('/api/pagina?id=' + encodeURIComponent(pid));
  estado.pagina = p; estado.linhasPagina = p.linhas; estado.linha = null;
  for (const b of document.querySelectorAll('#faixa [data-pag]'))
    b.classList.toggle('ativa', b.dataset.pag === pid);
  desenharVisor();
  const destino = (linhaAlvo && p.linhas.some((l) => l.id === linhaAlvo)) ? linhaAlvo
    : (p.linhas.find((l) => l.exige_revisao) || p.linhas[0] || null);
  if (destino) await selecionarLinha(destino.id || destino);
  else $('tab-linha').innerHTML = '<p class="vazio">Página sem linhas.</p>';
}
function desenharVisor() {
  const p = estado.pagina, box = $('visor-dentro');
  const W = p.largura || 800, H = p.altura || 1000;
  const rects = estado.linhasPagina.map((l) => {
    const cls = l.id === estado.linha ? 'caixa sel' : ('caixa ' + (l.confianca == null || l.confianca < 0.7 ? 'baixa-c' : (l.confianca >= 0.85 ? 'ok-c' : '')));
    const w = Math.max(l.largura, 4), h = Math.max(l.altura, 4);
    return '<rect class="' + cls + '" data-caixa="' + l.id + '" x="' + l.x + '" y="' + l.y +
      '" width="' + w + '" height="' + h + '"><title>l.' + l.numero + ' · ' + confTxt(l.confianca) + '</title></rect>';
  }).join('');
  box.style.width = Math.round(estado.zoom * 100) + '%';
  $('zoom-rotulo').textContent = Math.round(estado.zoom * 100) + '%';
  box.innerHTML = '<img src="/api/pagina/imagem?id=' + p.id + '&tipo=' + estado.camada + '" alt="página ' + p.numero + '">' +
    '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none">' + rects + '</svg>';
  for (const r of box.querySelectorAll('[data-caixa]'))
    r.onclick = (ev) => { ev.stopPropagation(); selecionarLinha(r.dataset.caixa); };
  desenharLista();
}
function desenharLista() {
  const ls = estado.linhasPagina;
  let html;
  if (!ls.length) html = '<p class="vazio">Página sem linhas.</p>';
  else html = '<div class="lista-linhas">' + ls.map((l) =>
    '<button type="button" class="row-linha' + (l.id === estado.linha ? ' sel' : '') + '" data-rlinha="' + l.id + '">' +
    '<span class="ponto ' + (l.confianca == null || l.confianca < 0.7 ? 'baixa' : (l.confianca < 0.85 ? 'media' : 'alta-c')) + '"></span>' +
    '<span class="txt"><strong>l.' + l.numero + '</strong> ' + esc((l.texto || '').slice(0, 70)) + '</span>' +
    '<span class="st st-' + l.status + '">' + confTxt(l.confianca) + '</span></button>').join('') + '</div>';
  const antiga = $('lista-pag');
  if (antiga) antiga.remove();
  const div = document.createElement('div');
  div.id = 'lista-pag'; div.hidden = !$('aba-linha').classList.contains('ativa'); div.innerHTML = html;
  $('tab-linha').before(div);
  for (const b of div.querySelectorAll('[data-rlinha]'))
    b.onclick = () => selecionarLinha(b.dataset.rlinha);
}
async function selecionarLinha(lid) {
  estado.linha = lid;
  const base = estado.linhasPagina.find((l) => l.id === lid);
  const d = await api('/api/linha?id=' + encodeURIComponent(lid));
  estado.detalhe = d;
  desenharVisor();
  const st = (base && base.status) || d.status;
  $('tab-linha').innerHTML =
    '<img class="recorte" src="/api/linha/imagem?id=' + lid + '" alt="recorte da linha">' +
    '<div class="meta-linha"><span class="conf ' + confClasse(d.confianca) + '">' + confTxt(d.confianca) + '</span>' +
    '<span class="st st-' + st + '">' + st + '</span></div>' +
    '<details class="camadas"><summary>texto bruto (nunca editado)</summary><pre>' + esc(d.texto_bruto) + '</pre></details>' +
    '<details class="camadas"><summary>texto normalizado</summary><pre>' + esc(d.texto_normalizado || '—') + '</pre></details>' +
    '<label class="dica" for="ed-diplo">texto diplomático (editável — Ctrl+Enter salva)</label>' +
    '<textarea class="diplo" id="ed-diplo" rows="4">' + esc(d.texto_diplomatico) + '</textarea>' +
    '<div class="botoes"><button class="primario" id="btn-salvar" type="button">Salvar e marcar revisada</button>' +
    '<button id="btn-ileg" type="button">Ilegível <kbd>2</kbd></button>' +
    '<button id="btn-treino" type="button">Treinamento <kbd>3</kbd></button></div>' +
    '<div class="botoes"><button id="btn-ver-sug" type="button">Ver sugestões LLM</button>' +
    '<button id="btn-pedir-sug" type="button">Pedir sugestão LLM</button></div>' +
    '<div id="box-sug"></div>' +
    '<h3 style="font-size:.9rem;color:var(--text-2)">Histórico auditado</h3><ul class="hist" id="hist"></ul>';
  const ed = $('ed-diplo'), btnS = $('btn-salvar');
  ed.oninput = () => btnS.classList.toggle('sujo', ed.value !== (d.texto_diplomatico || ''));
  btnS.onclick = salvar;
  $('btn-ileg').onclick = () => marcar('ilegivel');
  $('btn-treino').onclick = () => marcar('treinamento');
  $('btn-ver-sug').onclick = () => verSugestoes(false);
  $('btn-pedir-sug').onclick = pedirSugestao;
  $('hist').innerHTML = (d.historico || []).map((h) =>
    '<li><strong>' + esc(h.origem) + '</strong> por ' + esc(h.usuario || '—') + ' · ' + esc(h.data || '') +
    '<br>' + esc((h.anterior || '') .slice(0, 80)) + ' → ' + esc((h.corrigido || '').slice(0, 80)) + '</li>').join('') ||
    '<li>sem correções registradas</li>';
  verSugestoes(true);
}
async function salvar() {
  const btn = $('btn-salvar');
  if (!estado.linha || !btn || btn.disabled) return;
  btn.disabled = true;
  try {
    await api('/api/corrigir', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ linha_id: estado.linha, texto: $('ed-diplo').value }) });
    toast('Salvo e marcado como revisada.');
    await recarregarAposAcao();
  } catch (e) { toast(String(e.message || e), true); btn.disabled = false; }
}
async function marcar(stt) {
  if (!estado.linha) return;
  try {
    await api('/api/marcar', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ linha_id: estado.linha, status: stt }) });
    toast(stt === 'ilegivel' ? 'Marcada como ilegível.' : 'Marcada para treinamento.');
    await recarregarAposAcao();
  } catch (e) { toast(String(e.message || e), true); }
}
async function recarregarAposAcao() {
  const lid = estado.linha;
  const p = await api('/api/pagina?id=' + encodeURIComponent(estado.pagina.id));
  estado.linhasPagina = p.linhas;
  const pos = Math.max(p.linhas.findIndex((l) => l.id === lid), 0);
  const proxima = p.linhas.slice(pos + 1).find((l) => l.exige_revisao)
    || p.linhas.slice(0, pos + 1).find((l) => l.exige_revisao);
  if (proxima) await selecionarLinha(proxima.id);
  else if (lid) await selecionarLinha(lid);
  try {
    if (estado.doc && $('fila-doc')) {
      const fila = await api('/api/revisao?documento=' + encodeURIComponent(estado.doc.id) + '&limite=200');
      estado.filaDoc = fila.linhas;
      $('fila-doc').innerHTML = fila.linhas.map((l) => itemFilaHtml(l, false)).join('') || '<p class="vazio">Sem fila neste documento.</p>';
      ligarFila($('fila-doc'));
    }
    await carregarPainel();
  } catch (e) { /* painel/filas são auxiliares; o salvamento já ocorreu */ }
}
function verSugestoes(silencioso) {
  const box = $('box-sug'); if (!box) return;
  const d = estado.detalhe || {};
  if (!d.sugestoes || !d.sugestoes.length) { if (!silencioso) box.innerHTML = '<p class="dica">Sem sugestões LLM registradas.</p>'; return; }
  box.innerHTML = d.sugestoes.map((s) =>
    '<div class="sugestao"><strong>sugestão LLM:</strong> ' + esc(s.texto) +
    '<br><small>' + esc(s.data || '') + ' — confirme visualmente e salve para aplicar</small></div>').join('');
}
async function pedirSugestao() {
  const box = $('box-sug'); box.innerHTML = '<p class="dica">Consultando LLM local…</p>';
  try {
    const j = await api('/api/sugerir', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ linha_id: estado.linha }) });
    box.innerHTML = '<div class="sugestao"><strong>sugestão LLM (' + esc(j.tipo || '?') + ' · ' +
      Math.round((j.confianca ?? 0) * 100) + '%):</strong> ' + esc(j.sugestao) +
      '<br><small>' + esc(j.justificativa || '') + '</small></div>';
  } catch (e) { box.innerHTML = '<p class="dica">Falha: ' + esc(e.message) + '</p>'; }
}
async function exportar() {
  const msg = $('exp-msg'); msg.textContent = 'exportando…';
  try {
    const j = await api('/api/exportar-dataset', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ colecao: $('colecao').value || 'revisao_web' }) });
    msg.textContent = 'adicionadas=' + j.adicionadas + ' ignoradas=' + j.ignoradas;
    toast('Ground truth atualizado: +' + j.adicionadas + ' linhas.');
  } catch (e) { msg.textContent = 'Falha: ' + e.message; }
}
/* ---------- OCR Studio: abas, upload, preferências ---------- */
function irPainel() {
  estado.doc = null; $('view-doc').hidden = true; $('view-painel').hidden = false;
  $('tabConverter').classList.add('active'); $('tabDocs').classList.remove('active');
  Promise.all([carregarDocs(), carregarPainel()]);
}
function salvarPrefs() {
  try {
    const langs = document.querySelectorAll('#langChips .chip');
    const fmt = document.querySelector('.fmt.selected');
    const opts = {};
    document.querySelectorAll('#ocrToggles input').forEach((c) => { opts[c.dataset.opt] = c.checked; });
    localStorage.setItem('ocrstudio.prefs', JSON.stringify({
      langs: Array.from(langs).map((c) => c.classList.contains('selected')),
      fmt: fmt ? fmt.textContent.slice(0, 12) : '',
      opts: opts,
       engine: ($('selMotor') || {}).value || 'auto',
    }));
  } catch (e) { /* sem localStorage: ignora */ }
}
function restaurarPrefs() {
  let p = null;
  try { p = JSON.parse(localStorage.getItem('ocrstudio.prefs') || 'null'); } catch (e) { p = null; }
  if (!p) return;
  const chips = document.querySelectorAll('#langChips .chip');
  chips.forEach((c, i) => {
    const on = !!(p.langs && p.langs[i]);
    c.classList.toggle('selected', on); c.setAttribute('aria-checked', on);
  });
  if (p.fmt) {
    document.querySelectorAll('.fmt').forEach((f) => {
      const on = f.textContent.slice(0, 12) === p.fmt;
      f.classList.toggle('selected', on); f.setAttribute('aria-checked', on);
    });
  }
  if (p.engine && $('selMotor')) {
     let eng = p.engine === 'paddle_vl' ? 'qwen3_vl' : p.engine;
     const op = Array.from($('selMotor').options).find((x) => x.value === eng && !x.disabled);
     if (op) $('selMotor').value = eng;
   }
   if (p.opts) {
    document.querySelectorAll('#ocrToggles input').forEach((c) => { c.checked = !!p.opts[c.dataset.opt]; });
  }
}
desenharMotorAtual();
carregarPaddleStatus(true);
function selecionarMotorVisual(motor) {
  const sel = $('selMotor');
  if (!sel) return;
  sel.value = motor;
  salvarPrefs();
  desenharMotorAtual();
  carregarPaddleStatus(false);
  $('enginePanel').scrollIntoView({ behavior: 'smooth', block: 'center' });
}
/* ---------- eventos ---------- */
$('selMotor').onchange = () => { salvarPrefs(); desenharMotorAtual(); desenharChipsVisuais(); carregarPaddleStatus(true); };
$('btnAtualizarMotores').onclick = () => { carregarMotores(false); carregarPaddleStatus(false); };
$('btnPaddleVL').onclick = alternarPaddleVL;
if ($('chkGpu')) $('chkGpu').onchange = () => salvarPrefs();
let buscaTimer = null;
$('busca').oninput = () => {
  if (buscaTimer) clearTimeout(buscaTimer);
  buscaTimer = setTimeout(() => carregarDocs(), 240);
};
$('filtro-doc').onchange = () => carregarDocs();
$('tabConverter').onclick = irPainel;
$('tabDocs').onclick = () => {
  $('tabConverter').classList.remove('active'); $('tabDocs').classList.add('active');
  if (!$('view-doc').hidden) { irPainel(); return; }
  const el = $('cardDocs'); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
};
$('btn-voltar').onclick = irPainel;
$('camada').onchange = (e) => { estado.camada = e.target.value; desenharVisor(); };
$('zoom-mais').onclick = () => { estado.zoom = Math.min(3, estado.zoom + 0.25); desenharVisor(); };
$('zoom-menos').onclick = () => { estado.zoom = Math.max(0.5, estado.zoom - 0.25); desenharVisor(); };
$('zoom-ajustar').onclick = () => { estado.zoom = 1; desenharVisor(); };
$('btn-exportar').onclick = exportar;
$('btnConvert').onclick = () => enfileirarOcr(null, false);
const btnUp = $('btnUpload');
if (btnUp) btnUp.onclick = () => {
  const sec = $('dropzone');
  if (sec) sec.scrollIntoView({ behavior: 'smooth', block: 'center' });
  $('fileInput').focus({ preventScroll: true });
};
$('btnRepro').onclick = async () => {
  toast('Reconhecendo pendentes e documentos com erro…');
  await enfileirarOcr(null, false);
};
$('btnDlAll').onclick = async () => {
  const docs = (estado.docs || []).filter((d) => d.status === 'concluido' || d.status === 'parcial');
  if (!docs.length) { toast('Nenhum documento reconhecido para baixar.', true); return; }
  for (const d of docs) { await baixarProdutos(d.id); }
};
$('lnkAjuda').onclick = (e) => { e.preventDefault(); toast('Docs em docs/USO.md — seção Estação de revisão local.'); };
$('lnkTermos').onclick = (e) => { e.preventDefault(); toast('Uso local e auditável — nada é enviado para a nuvem.'); };
const dz = $('dropzone'), fi = $('fileInput');
let arquivosPendentes = [];
function mostrarPendentes() {
  const lista = $('dropLista'), btn = $('btnEnviar');
  lista.innerHTML = arquivosPendentes.map((f) =>
    '<li>' + esc(f.name) + ' <span class="dica">' + (f.size / 1024).toFixed(0) + ' KB</span></li>').join('');
  btn.textContent = arquivosPendentes.length
    ? 'Enviar e reconhecer (' + arquivosPendentes.length + ')' : 'Enviar e reconhecer';
  btn.disabled = !arquivosPendentes.length;
  $('dropHint').textContent = arquivosPendentes.length
    ? arquivosPendentes.length + ' arquivo(s) pronto(s) — confira o motor e clique em Enviar'
    : 'PDF, JPG, PNG, TIFF — clique para selecionar ou solte os arquivos';
}
async function enviarPendentes() {
  if (!arquivosPendentes.length) { toast('Selecione ao menos um arquivo.', true); return; }
  const btn = $('btnEnviar'); btn.disabled = true;
  const track = $('progressTrack'); if (track) track.classList.remove('idle');
  try {
    const form = new FormData();
    for (const f of arquivosPendentes) form.append('arquivo', f, f.name);
    const querOcr = !$('chkProcessar') || $('chkProcessar').checked;
    if (querOcr) form.append('processar', '1');
    const sel = $('selMotor'); if (sel && sel.value) form.append('engine', sel.value);
    const r = await fetch('/api/upload', { method: 'POST', body: form });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.erro || ('HTTP ' + r.status));
    const oks = (j.arquivos || []).filter((a) => a.status === 'ok').length;
    const erros = (j.arquivos || []).filter((a) => a.status !== 'ok');
    toast('Enviados: ' + oks + ' ok, novos=' + j.novos + ', pulados=' + j.pulados +
      (j.trabalho ? ' — OCR iniciado, acompanhe abaixo.' : ''));
    if (j.processar_erro) toast(j.processar_erro, true);
    for (const a of erros) toast(a.nome + ': ' + a.motivo, true);
    if (j.trabalho) desenharTrabalho(j.trabalho);
    arquivosPendentes = []; fi.value = ''; mostrarPendentes();
    await Promise.all([carregarDocs(), carregarPainel()]);
    if (j.trabalho) iniciarSondagem();
  } catch (e) { toast('Falha no envio: ' + e.message, true); }
  finally { btn.disabled = !arquivosPendentes.length; if (track) track.classList.add('idle'); }
}
if (dz && fi) {
  ['dragover', 'dragenter'].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add('dragover'); }));
  ['dragleave', 'drop'].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove('dragover'); }));
  dz.addEventListener('drop', (e) => {
    e.preventDefault();
    arquivosPendentes = Array.from(e.dataTransfer.files || []);
    mostrarPendentes();
  });
  fi.addEventListener('change', () => {
    arquivosPendentes = Array.from(fi.files || []);
    mostrarPendentes();
  });
  $('btnEnviar').onclick = enviarPendentes;
  const bc = $('btnCancelar');
  if (bc) bc.onclick = async () => {
    try { const t = await api('/api/cancelar', { method: 'POST' }); desenharTrabalho(t); }
    catch (e) { toast('Falha ao cancelar: ' + e.message, true); }
  };
  mostrarPendentes();
}
document.querySelectorAll('#langChips .chip').forEach((c) => {
  const t = () => { c.classList.toggle('selected');
    c.setAttribute('aria-checked', c.classList.contains('selected')); salvarPrefs(); };
  c.addEventListener('click', t);
  c.addEventListener('keydown', (e) => { if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); t(); } });
});
document.querySelectorAll('#fmtGrid .fmt').forEach((f) => {
  const s = () => {
    document.querySelectorAll('#fmtGrid .fmt').forEach((x) => { x.classList.remove('selected'); x.setAttribute('aria-checked', 'false'); });
    f.classList.add('selected'); f.setAttribute('aria-checked', 'true'); salvarPrefs();
  };
  f.addEventListener('click', s);
  f.addEventListener('keydown', (e) => { if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); s(); } });
});
document.querySelectorAll('#ocrToggles input').forEach((c) => c.addEventListener('change', salvarPrefs));
$('aba-linha').onclick = () => { $('aba-linha').classList.add('ativa'); $('aba-fila').classList.remove('ativa'); $('tab-linha').hidden = false; const lp = $('lista-pag'); if (lp) lp.hidden = false; $('tab-fila').hidden = true; };
$('aba-fila').onclick = () => { $('aba-fila').classList.add('ativa'); $('aba-linha').classList.remove('ativa'); $('tab-fila').hidden = false; const lp = $('lista-pag'); if (lp) lp.hidden = true; $('tab-linha').hidden = true; };
document.addEventListener('keydown', (e) => {
  if ($('view-doc').hidden || !estado.pagina) return;
  const tag = (document.activeElement || {}).tagName;
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && $('ed-diplo')) { e.preventDefault(); salvar(); return; }
  if (tag === 'TEXTAREA' || tag === 'INPUT' || tag === 'SELECT') return;
  const ids = estado.linhasPagina.map((l) => l.id);
  const i = ids.indexOf(estado.linha);
  if (e.key === 'ArrowDown' || e.key === 'j') { e.preventDefault(); if (ids[i + 1]) selecionarLinha(ids[i + 1]); }
  else if (e.key === 'ArrowUp' || e.key === 'k') { e.preventDefault(); if (ids[i - 1]) selecionarLinha(ids[i - 1]); }
  else if (e.key === 'ArrowRight') { e.preventDefault(); trocarPagina(1); }
  else if (e.key === 'ArrowLeft') { e.preventDefault(); trocarPagina(-1); }
  else if (e.key === '1') marcar('revisada');
  else if (e.key === '2') marcar('ilegivel');
  else if (e.key === '3') marcar('treinamento');
});
function trocarPagina(delta) {
  const idx = estado.paginas.findIndex((p) => p.id === estado.pagina.id);
  const alvo = estado.paginas[idx + delta];
  if (alvo) carregarPagina(alvo.id);
}
boot();
</script>
</body>
</html>
"""
