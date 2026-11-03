"""Interface de linha de comando do OCR Histórico BR."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from .config import AppConfig, carregar_config
from .database import fabrica_sessoes, inicializar_banco
from .diagnostico import coletar_diagnostico, diagnostico_para_json

logger = logging.getLogger("ocr_historico")

app = typer.Typer(
    name="ocrhist",
    help="OCR e HTR local e auditável para documentos históricos brasileiros.",
    no_args_is_help=True,
    add_completion=False,
    invoke_without_command=True,
)
dataset_app = typer.Typer(name="dataset", help="Gerenciamento de datasets de linhas.", no_args_is_help=True)
app.add_typer(dataset_app, name="dataset")
treinar_app = typer.Typer(name="treinar", help="Treinamento e avaliação de modelos HTR.", no_args_is_help=True)
app.add_typer(treinar_app, name="treinar")


@app.callback()
def callback(
    version: Annotated[bool, typer.Option("--version", help="Exibe a versão instalada.")] = False,
    log_nivel: Annotated[
        str,
        typer.Option(
            "--log-nivel",
            help="Nível de log: DEBUG, INFO, WARNING, ERROR (padrão: INFO).",
        ),
    ] = "INFO",
) -> None:
    """Comandos de fundação do OCR Histórico BR."""
    from .logging_config import configurar_logging

    configurar_logging(jsonl=False)
    nivel = getattr(logging, log_nivel.upper(), logging.INFO)
    logging.getLogger("ocr_historico").setLevel(nivel)
    if version:
        from . import __version__

        typer.echo(__version__)
        raise typer.Exit()


def raiz_projeto() -> Path:
    return Path(__file__).resolve().parents[2]


def caminho_config_padrao() -> Path:
    return raiz_projeto() / "configs" / "default.yaml"


def _caminho_entrada_valido(caminho: Path) -> Path:
    """Valida que o caminho de entrada existe e é arquivo ou diretório.

    Retorna o caminho resolvido. Levanta ``typer.BadParameter`` com mensagem
    amigável (sem stack trace) para erros de uso do CLI.
    """
    base = Path(caminho).expanduser()
    if not base.exists():
        raise typer.BadParameter(f"Caminho de entrada não encontrado: {base}", param_hint="CAMINHO")
    if not (base.is_file() or base.is_dir()):
        raise typer.BadParameter(
            f"Caminho de entrada não é arquivo nem diretório: {base}",
            param_hint="CAMINHO",
        )
    return base


def obter_config(caminho: Path | None) -> AppConfig:
    return carregar_config(caminho or caminho_config_padrao())


def aplicar_perfil(dados: AppConfig, nome: str) -> AppConfig:
    """Aplica um perfil do diretório ``configs`` preservando caminhos locais."""
    if not nome or nome == "automatico":
        return dados
    caminho = raiz_projeto() / "configs" / f"{nome}.yaml"
    if not caminho.is_file():
        raise ValueError(f"Perfil não encontrado: {nome} (esperado: {caminho})")
    perfil = carregar_config(caminho)
    base = dados.model_dump()
    aplicado = perfil.model_dump()
    for campo in ("entrada", "saida", "banco"):
        aplicado[campo] = base[campo]
    # O perfil é uma sobreposição; opções operacionais do YAML principal ficam.
    for campo in ("inventario", "preservacao", "workers", "salvar_imagens", "ocrmypdf"):
        aplicado[campo] = base[campo]
    return AppConfig.model_validate(aplicado)


@app.command("inventariar")
def inventariar(
    caminho: Annotated[Path, typer.Argument(help="Arquivo ou diretório a inventariar.")],
    destino: Annotated[Path | None, typer.Option("--destino", "-o", help="Pasta dos manifestos.")] = None,
    sem_hash: Annotated[bool, typer.Option("--sem-hash", help="Não calcula SHA-256.")] = False,
) -> None:
    """Gera inventário CSV/JSON sem executar OCR e sem alterar a entrada."""
    from .ingestao.inventario import inventariar_entrada, salvar_inventario

    caminho = _caminho_entrada_valido(caminho)
    try:
        resultado = inventariar_entrada(caminho, calcular_hash=not sem_hash)
        arquivos = salvar_inventario(resultado, destino or Path("inventario"))
    except (FileNotFoundError, OSError, ValueError) as erro:
        typer.echo(f"ERRO: {erro}")
        raise typer.Exit(code=2) from erro
    typer.echo(
        f"Inventário: {len(resultado.suportados)} suportado(s), "
        f"{len(resultado.ignorados)} ignorado(s). JSON: {arquivos['json']} CSV: {arquivos['csv']}"
    )


@app.command("setup")
def setup(
    config: Annotated[Path | None, typer.Option("--config", "-c", help="Arquivo YAML de configuração.")] = None,
    criar_diretorios: Annotated[
        bool, typer.Option("--criar-diretorios", help="Cria entrada e saída após confirmação.")
    ] = False,
    confirmar: Annotated[bool, typer.Option("--sim", help="Confirma criação sem pergunta interativa.")] = False,
) -> None:
    """Valida a configuração e inicializa o banco local sem baixar modelos."""
    try:
        dados = obter_config(config)
    except (FileNotFoundError, ValueError, ValidationError) as erro:
        raise typer.BadParameter(str(erro), param_hint="--config") from erro

    if criar_diretorios:
        destinos = [dados.entrada, dados.saida]
        inexistentes = [destino for destino in destinos if not destino.exists()]
        if inexistentes and not confirmar:
            texto = ", ".join(str(destino) for destino in inexistentes)
            if not typer.confirm(f"Criar os diretórios ausentes? {texto}", default=False):
                raise typer.Abort()
        for destino in inexistentes:
            destino.mkdir(parents=True, exist_ok=True)
            typer.echo(f"Criado: {destino}")
    elif not dados.entrada.exists() or not dados.saida.exists():
        typer.echo("Diretórios padrão ausentes; nada foi criado. Use --criar-diretorios para confirmar.")

    inicializar_banco(dados.banco)
    typer.echo(f"Banco SQLite inicializado: {dados.banco}")
    typer.echo("Setup concluído. Nenhum modelo foi baixado e nenhum documento foi alterado.")


@app.command("diagnosticar")
@app.command("doctor")
def diagnosticar(
    config: Annotated[Path | None, typer.Option("--config", "-c", help="Arquivo YAML de configuração.")] = None,
    json_saida: Annotated[bool, typer.Option("--json", help="Emite JSON em vez de texto.")] = False,
    strict: Annotated[bool, typer.Option("--strict", help="Retorna código 1 se houver falha.")] = False,
) -> None:
    """Exibe a disponibilidade de dependências obrigatórias e opcionais."""
    try:
        dados = obter_config(config)
    except (FileNotFoundError, ValueError, ValidationError) as erro:
        typer.echo(f"ERRO de configuração: {erro}")
        raise typer.Exit(code=2) from erro
    itens = coletar_diagnostico(dados, raiz_projeto())
    if json_saida:
        typer.echo(json.dumps(diagnostico_para_json(itens), ensure_ascii=False, indent=2))
    else:
        for item in itens:
            typer.echo(f"{item.nome}: {item.estado} — {item.detalhe}")
    if strict and any(item.estado in {"ERRO", "INDISPONÍVEL"} for item in itens):
        raise typer.Exit(code=1)


@app.command("processar")
def processar(
    caminho: Annotated[Path, typer.Argument(help="Arquivo ou diretório a ingerir.")],
    config: Annotated[Path | None, typer.Option("--config", "-c", help="Arquivo YAML de configuração.")] = None,
    perfil: Annotated[str | None, typer.Option("--perfil", help="Perfil documental.")] = None,
    saida: Annotated[Path | None, typer.Option("--saida", help="Diretório de saída (produtos futuros).")] = None,
    dpi: Annotated[int | None, typer.Option("--dpi", help="DPI de renderização do PDF.")] = None,
    workers: Annotated[int, typer.Option("--workers", help="Trabalhadores (reservado; Marco 2 é sequencial).")] = 1,
    forcar: Annotated[bool, typer.Option("--forcar", help="Reprocessa arquivos já concluídos.")] = False,
    retry_failed: Annotated[bool, typer.Option("--retry-failed", help="Tenta novamente arquivos com falha.")] = False,
    engine: Annotated[
        str | None,
        typer.Option(
            "--engine",
            help="Motor: auto, tesseract, paddleocr, kraken, qwen3_vl, glm_ocr, olmocr, pdf_texto ou ensemble.",
        ),
    ] = None,
    vl_url: Annotated[
        str | None,
        typer.Option("--vl-url", help="Base do llama-server VLM (qwen3_vl/glm_ocr/olmocr: :8082)."),
    ] = None,
    vl_modelo: Annotated[
        str | None,
        typer.Option("--vl-modelo", help="Modelo VLM servido (ex. Qwen3VL-4B-Instruct, GLM-OCR, olmOCR-2-7B)."),
    ] = None,
    somente_ingestao: Annotated[
        bool, typer.Option("--somente-ingestao", help="Só descobre e registra, sem OCR.")
    ] = False,
) -> None:
    """Descobre arquivos, registra no banco e executa o OCR em lote."""
    from pydantic import ValidationError

    from .ingestao import ingerir_entrada

    caminho = _caminho_entrada_valido(caminho)
    try:
        dados = aplicar_perfil(obter_config(config), perfil or "automatico")
    except (FileNotFoundError, ValueError, ValidationError) as erro:
        typer.echo(f"ERRO de configuração/perfil: {erro}")
        raise typer.Exit(code=2) from erro
    if saida is not None:
        dados.saida = saida
    if dpi is not None:
        if dpi < 72 or dpi > 1200:
            typer.echo("ERRO: --dpi deve estar entre 72 e 1200.")
            raise typer.Exit(code=2)
        dados.render_dpi = dpi
    if workers != 1:
        dados.workers = workers
    try:
        resumo = ingerir_entrada(caminho, dados, perfil=perfil, forcar=forcar, retry_failed=retry_failed)
    except FileNotFoundError as erro:
        typer.echo(f"ERRO: {erro}")
        raise typer.Exit(code=2) from erro
    typer.echo(
        f"Ingestão concluída: {resumo.novos} novo(s), {resumo.pulados} pulado(s), "
        f"{resumo.erros} erro(s) em {resumo.total} arquivo(s); "
        f"inventário={resumo.inventariados}, ignorados={resumo.ignorados}."
    )
    if somente_ingestao:
        if resumo.erros:
            raise typer.Exit(code=1)
        return
    from .pipeline import processar_documentos

    ocr = processar_documentos(
        dados, engine_nome=engine, forcar=forcar, retry_failed=retry_failed, vl_url=vl_url, vl_modelo=vl_modelo
    )
    typer.echo(
        f"OCR concluído: {ocr.documentos} documento(s), {ocr.paginas_ok} página(s) ok, {ocr.paginas_erro} com erro."
    )
    if resumo.erros or ocr.paginas_erro:
        raise typer.Exit(code=1)


@app.command("listar")
def listar(
    status: Annotated[str | None, typer.Option("--status", help="Filtra por status.")] = None,
    config: Annotated[Path | None, typer.Option("--config", "-c", help="Arquivo YAML de configuração.")] = None,
) -> None:
    """Lista documentos registrados e seu estado."""
    from sqlalchemy import select

    from .models import Documento

    dados = obter_config(config)
    engine = inicializar_banco(dados.banco)
    with fabrica_sessoes(engine)() as sessao:
        consulta = select(Documento).order_by(Documento.criado_em)
        if status:
            consulta = consulta.where(Documento.status == status)
        documentos = list(sessao.scalars(consulta))
    if not documentos:
        typer.echo("Nenhum documento registrado.")
        return
    for doc in documentos:
        typer.echo(f"{doc.id} | {doc.nome_original} | {doc.tipo_arquivo} | {doc.numero_paginas} pág. | {doc.status}")


@app.command("status")
def status(
    documento_ou_id: Annotated[str | None, typer.Argument(help="ID ou nome do documento.")] = None,
    config: Annotated[Path | None, typer.Option("--config", "-c", help="Arquivo YAML de configuração.")] = None,
) -> None:
    """Exibe o andamento da ingestão, geral ou de um documento."""
    from sqlalchemy import func, or_, select

    from .models import Documento, Pagina

    dados = obter_config(config)
    engine = inicializar_banco(dados.banco)
    with fabrica_sessoes(engine)() as sessao:
        if documento_ou_id is None:
            linhas = sessao.execute(select(Documento.status, func.count(Documento.id)).group_by(Documento.status)).all()
            if not linhas:
                typer.echo("Nenhum documento registrado.")
                return
            for estado, total in linhas:
                typer.echo(f"{estado}: {total}")
            return
        doc = sessao.scalar(
            select(Documento).where(
                or_(
                    Documento.id == documento_ou_id,
                    Documento.nome_original == documento_ou_id,
                    Documento.caminho_original == documento_ou_id,
                )
            )
        )
        if doc is None:
            typer.echo(f"Documento não encontrado: {documento_ou_id}")
            raise typer.Exit(code=2)
        typer.echo(f"{doc.nome_original} | {doc.tipo_arquivo} | {doc.numero_paginas} pág. | {doc.status}")
        if doc.erro:
            typer.echo(f"Erro: {doc.erro}")
        paginas = sessao.scalars(select(Pagina).where(Pagina.documento_id == doc.id).order_by(Pagina.numero)).all()
        for pagina in paginas:
            typer.echo(f"  pág. {pagina.numero}: {pagina.status} ({pagina.largura}x{pagina.altura})")


@app.command("avaliar")
def avaliar(
    referencia: Annotated[Path, typer.Option("--referencia", help="Arquivo de referência/ground truth.")],
    hipotese: Annotated[Path, typer.Option("--hipotese", help="Arquivo de hipótese OCR.")],
    normalizar: Annotated[
        bool, typer.Option("--normalizar", help="Normaliza espaços, caixa e bordas antes de medir.")
    ] = False,
    relatorio: Annotated[Path | None, typer.Option("--relatorio", help="Salva o relatório JSON neste caminho.")] = None,
) -> None:
    """Calcula CER e WER; valores menores significam menos erros, não acurácia."""
    from .avaliacao.comparacao import avaliar_arquivos

    try:
        cer, wer = avaliar_arquivos(referencia, hipotese, normalizar=normalizar)
    except OSError as erro:
        typer.echo(f"ERRO ao ler arquivos: {erro}")
        raise typer.Exit(code=2) from erro
    typer.echo("Métricas (CER/WER são taxas de erro; não são acurácia):")
    typer.echo(
        f"CER: {cer.valor:.4f} | distância={cer.distancia} referência={cer.referencia} "
        f"inserções={cer.insercoes} deleções={cer.delecoes} substituições={cer.substituicoes}"
    )
    typer.echo(
        f"WER: {wer.valor:.4f} | distância={wer.distancia} referência={wer.referencia} "
        f"inserções={wer.insercoes} deleções={wer.delecoes} substituições={wer.substituicoes}"
    )
    if relatorio:
        import json

        relatorio.parent.mkdir(parents=True, exist_ok=True)
        relatorio.write_text(
            json.dumps(
                {"modo_normalizacao": normalizar, "cer": cer.as_dict(), "wer": wer.as_dict()},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        typer.echo(f"Relatório JSON: {relatorio}")


@app.command("revisar")
def revisar(
    banco: Annotated[Path | None, typer.Option("--banco", help="Banco SQLite.")] = None,
    status_revisao: Annotated[str | None, typer.Option("--status", help="Status a filtrar.")] = None,
    limite: Annotated[int, typer.Option("--limite", min=1, max=10000, help="Máximo de linhas.")] = 100,
    config: Annotated[Path | None, typer.Option("--config", "-c", help="Arquivo YAML.")] = None,
) -> None:
    """Lista a fila de revisão ordenada por incerteza."""
    from .revisao import listar_fila

    dados = obter_config(config)
    try:
        itens = listar_fila(banco or dados.banco, status=status_revisao, limite=limite)
    except ValueError as erro:
        typer.echo(f"ERRO: {erro}")
        raise typer.Exit(code=2) from erro
    if not itens:
        typer.echo("Fila de revisão vazia.")
        return
    for item in itens:
        conf = "—" if item.confianca is None else f"{item.confianca:.3f}"
        typer.echo(
            f"{item.linha_id} | {item.documento} | pág. {item.pagina} linha {item.numero} | "
            f"{item.prioridade} | conf. {conf} | {item.texto_diplomatico}"
        )


@app.command("corrigir")
def corrigir(
    linha_id: Annotated[str, typer.Argument(help="ID da linha.")],
    texto: Annotated[str, typer.Option("--texto", help="Texto diplomático corrigido.")],
    usuario: Annotated[str | None, typer.Option("--usuario", help="Identificação do revisor.")] = None,
    observacao: Annotated[str | None, typer.Option("--observacao", help="Nota auditável.")] = None,
    config: Annotated[Path | None, typer.Option("--config", "-c", help="Arquivo YAML.")] = None,
) -> None:
    """Corrige a transcrição diplomática e grava a trilha de auditoria."""
    from .revisao import corrigir_linha

    dados = obter_config(config)
    try:
        correcao = corrigir_linha(dados.banco, linha_id, texto, "humana", usuario, observacao)
    except ValueError as erro:
        typer.echo(f"ERRO: {erro}")
        raise typer.Exit(code=2) from erro
    typer.echo(f"Correção registrada: {correcao.id}")


@app.command("marcar")
def marcar(
    linha_id: Annotated[str, typer.Argument(help="ID da linha.")],
    status_revisao: Annotated[str, typer.Argument(help="revisada, ilegivel, treinamento ou pendente.")],
    usuario: Annotated[str | None, typer.Option("--usuario", help="Identificação do revisor.")] = None,
    observacao: Annotated[str | None, typer.Option("--observacao", help="Nota auditável.")] = None,
    config: Annotated[Path | None, typer.Option("--config", "-c", help="Arquivo YAML.")] = None,
) -> None:
    """Marca uma linha para revisão, como ilegível ou para treinamento."""
    from .revisao import marcar_linha

    dados = obter_config(config)
    try:
        marcar_linha(dados.banco, linha_id, status_revisao, usuario, observacao)
    except ValueError as erro:
        typer.echo(f"ERRO: {erro}")
        raise typer.Exit(code=2) from erro
    typer.echo(f"Linha marcada como {status_revisao}.")


@app.command("selecionar")
def selecionar(
    limite: Annotated[int, typer.Option("--limite", min=1, max=10000)] = 100,
    config: Annotated[Path | None, typer.Option("--config", "-c", help="Arquivo YAML.")] = None,
) -> None:
    """Seleciona linhas por aprendizado ativo para revisão prioritária."""
    from .avaliacao.active_learning import selecionar_linhas

    dados = obter_config(config)
    for item in selecionar_linhas(dados.banco, limite=limite):
        conf = "—" if item.confianca is None else f"{item.confianca:.3f}"
        typer.echo(f"{item.linha_id} | pontuação {item.pontuacao:.3f} | conf. {conf} | {item.texto}")


@app.command("sugerir")
def sugerir(
    linhas: Annotated[list[str] | None, typer.Option("--linha", help="ID da linha (pode repetir).")] = None,
    documento: Annotated[str | None, typer.Option("--documento", help="ID do documento (usa fila de revisão).")] = None,
    limite: Annotated[int, typer.Option("--limite", min=1, max=100, help="Máximo de linhas ao usar --documento.")] = 10,
    confirmar_lote: Annotated[
        bool, typer.Option("--confirmar-lote", help="Confirma envio de múltiplas linhas ao LLM local.")
    ] = False,
    usuario: Annotated[str | None, typer.Option("--usuario", help="Identificação do revisor.")] = None,
    config: Annotated[Path | None, typer.Option("--config", "-c", help="Arquivo YAML.")] = None,
) -> None:
    """Pede sugestões ao LLM local para linhas selecionadas (nunca altera o diplomático)."""
    from .posprocessamento.llm_revisor import sugerir_linhas
    from .revisao import listar_fila

    dados = obter_config(config)
    if not dados.llm.enabled:
        typer.echo("ERRO: LLM desabilitado (llm.enabled=false). Ative em configs/llm_local.yaml para usar --sugerir.")
        raise typer.Exit(code=2)
    ids: list[str] = list(linhas or [])
    if documento:
        fila = listar_fila(dados.banco, limite=10000)
        ids += [item.linha_id for item in fila if item.documento_id == documento][:limite]
    ids = list(dict.fromkeys(ids))
    if not ids:
        typer.echo("ERRO: informe --linha ID (repetível) ou --documento ID com --limite.")
        raise typer.Exit(code=2)
    if len(ids) > 1 and not confirmar_lote:
        typer.echo(f"ERRO: {len(ids)} linhas selecionadas. Confirme com --confirmar-lote para enviar ao LLM local.")
        raise typer.Exit(code=2)
    if len(ids) > 20:
        typer.echo("ERRO: máximo 20 linhas por chamada (envie em partes para revisão consciente).")
        raise typer.Exit(code=2)
    resultados = sugerir_linhas(
        dados.banco,
        ids,
        base_url=dados.llm.base_url,
        model=dados.llm.model,
        timeout_seconds=dados.llm.timeout_seconds,
        usuario=usuario,
    )
    ok = 0
    for res in resultados:
        if res.sugestao is None:
            typer.echo(f"{res.linha_id} | FALHA: {res.erro}")
            continue
        ok += 1
        typer.echo(f"{res.linha_id} | sugestão: {res.sugestao.sugestao} ")
        typer.echo(
            f"  tipo={res.sugestao.tipo} conf={res.sugestao.confianca:.2f} "
            f"revisão_visual={res.sugestao.exige_revisao_visual}"
        )
        typer.echo(f"  justificativa: {res.sugestao.justificativa_curta}")
    typer.echo(f"Sugestões: {ok}/{len(resultados)} (llm_sugerido, sem alterar diplomático).")
    if ok < len(resultados):
        raise typer.Exit(code=1)


@dataset_app.command("iniciar")
def dataset_iniciar(
    nome: Annotated[str, typer.Argument(help="Nome da coleção.")],
    raiz: Annotated[Path, typer.Option("--raiz", help="Diretório raiz do dataset.")] = Path("data/treinamento"),
) -> None:
    """Cria estrutura ground_truth para uma coleção."""
    from .treinamento.dataset import iniciar_dataset

    try:
        caminho = iniciar_dataset(nome, raiz)
    except ValueError as erro:
        typer.echo(f"ERRO: {erro}")
        raise typer.Exit(code=2) from erro
    typer.echo(f"Dataset criado: {caminho}")


@dataset_app.command("exportar")
def dataset_exportar(
    destino: Annotated[Path, typer.Argument(help="Diretório ground_truth da coleção.")],
    banco: Annotated[Path | None, typer.Option("--banco", help="Banco SQLite.")] = None,
    config: Annotated[Path | None, typer.Option("--config", "-c", help="Arquivo YAML.")] = None,
) -> None:
    """Exporta linhas marcadas como treinamento para ground truth."""
    from .treinamento.dataset import exportar_linhas_revisadas

    dados = obter_config(config)
    try:
        resultado = exportar_linhas_revisadas(banco or dados.banco, destino)
    except (OSError, ValueError) as erro:
        typer.echo(f"ERRO: {erro}")
        raise typer.Exit(code=2) from erro
    typer.echo(f"Dataset: {resultado.adicionadas} adicionada(s), {resultado.ignoradas} ignorada(s).")


@dataset_app.command("validar")
def dataset_validar(
    caminho: Annotated[Path, typer.Argument(help="Pasta ou manifest.jsonl.")],
) -> None:
    """Valida referências e transcrições de um dataset."""
    from .treinamento.dataset import validar_dataset

    erros = validar_dataset(caminho)
    if erros:
        for erro in erros:
            typer.echo(f"ERRO: {erro}")
        raise typer.Exit(code=1)
    typer.echo("Dataset válido.")


@dataset_app.command("dividir")
def dataset_dividir(
    caminho: Annotated[Path, typer.Argument(help="Manifesto ou pasta ground_truth.")],
    destino: Annotated[Path, typer.Option("--destino", help="Pasta de saída dos splits.")],
    grupo: Annotated[str, typer.Option("--grupo", help="documento ou escrevente.")] = "documento",
) -> None:
    """Divide dataset por documento/escrevente, evitando vazamento."""
    from .treinamento.split import dividir_manifesto

    try:
        contagem = dividir_manifesto(caminho, destino, grupo=grupo)
    except (OSError, ValueError) as erro:
        typer.echo(f"ERRO: {erro}")
        raise typer.Exit(code=2) from erro
    typer.echo("; ".join(f"{nome}: {total}" for nome, total in contagem.items()))


@treinar_app.command("kraken")
def treinar_kraken(
    dataset: Annotated[Path, typer.Argument(help="Pasta ground_truth ou manifest.jsonl do dataset.")],
    saida: Annotated[Path | None, typer.Option("--saida", "-o", help="Modelo .mlmodel de saída.")] = None,
    modelo_base: Annotated[
        Path | None, typer.Option("--modelo-base", help="Modelo base local para fine-tuning.")
    ] = None,
    epocas: Annotated[int, typer.Option("--epocas", min=1, max=1000, help="Número de épocas.")] = 20,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Apenas prepara e exibe o comando.")] = False,
    executar: Annotated[bool, typer.Option("--executar", help="Executa o treino (requer kraken/ketos).")] = False,
) -> None:
    """Prepara (e opcionalmente executa) fine-tuning Kraken — CPU-first, sem download silencioso."""
    from .treinamento.kraken_train import executar_treino, preparar_treino

    try:
        resultado = preparar_treino(dataset, saida=saida, modelo_base=modelo_base, epocas=epocas, dry_run=dry_run)
    except (OSError, ValueError) as erro:
        typer.echo(f"ERRO: {erro}")
        raise typer.Exit(code=2) from erro
    typer.echo(f"Comando: {' '.join(str(c) for c in resultado.comando)}")
    typer.echo(f"Saída: {resultado.modelo_saida}")
    if resultado.aviso:
        typer.echo(f"AVISO: {resultado.aviso}")
    if dry_run:
        typer.echo("Dry-run: nada executado.")
        return
    if not executar:
        typer.echo("Use --executar para iniciar o treino ou --dry-run para apenas validar.")
        return
    try:
        final = executar_treino(resultado, dry_run=False)
    except (FileNotFoundError, RuntimeError, OSError, ValueError) as erro:
        typer.echo(f"ERRO: {erro}")
        raise typer.Exit(code=1) from erro
    typer.echo(f"Treino concluído: {final.modelo_saida}")
    if final.log_path:
        typer.echo(f"Log: {final.log_path}")


@treinar_app.command("avaliar")
def treinar_avaliar(
    modelo: Annotated[Path, typer.Argument(help="Modelo .mlmodel treinado.")],
    teste: Annotated[Path, typer.Argument(help="Manifesto ou pasta de teste.")],
    relatorio: Annotated[Path | None, typer.Option("--relatorio", help="JSON de relatório.")] = None,
) -> None:
    """Avalia modelo Kraken no conjunto de teste separado (sem vazamento)."""
    from .treinamento.kraken_train import avaliar_modelo

    try:
        detalhe = avaliar_modelo(modelo, teste, relatorio=relatorio)
    except (OSError, ValueError) as erro:
        typer.echo(f"ERRO: {erro}")
        raise typer.Exit(code=2) from erro
    import json as _json

    typer.echo(_json.dumps(detalhe, ensure_ascii=False, indent=2))
    if detalhe.get("cer_medio") is not None:
        typer.echo(f"CER médio: {detalhe['cer_medio']:.4f} | WER médio: {detalhe.get('wer_medio')}")
    elif detalhe.get("aviso"):
        typer.echo(f"AVISO: {detalhe['aviso']}")


@app.command("web")
def web(
    host: Annotated[str, typer.Option("--host", help="Interface de escuta (padrão: local).")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", help="Porta do painel local.")] = 7860,
    expor_rede: Annotated[
        bool, typer.Option("--expor-rede", help="Permite escutar fora de localhost explicitamente.")
    ] = False,
    config: Annotated[Path | None, typer.Option("--config", "-c", help="Arquivo YAML de configuração.")] = None,
) -> None:
    """Inicia o painel local de revisão (imagem, overlay, 3 camadas de texto, LLM suggest_only)."""
    from .web.app import servir

    dados = obter_config(config)
    try:
        servir(dados, host=host, porta=port, expor_rede=expor_rede)
    except ValueError as erro:
        typer.echo(f"ERRO: {erro}")
        raise typer.Exit(code=2) from erro


@app.command("exportar")
def exportar(
    id_documento: Annotated[str, typer.Argument(help="ID do documento a exportar.")],
    config: Annotated[Path | None, typer.Option("--config", "-c", help="Arquivo YAML de configuração.")] = None,
) -> None:
    """Exporta TXT, Markdown e JSON sem repetir o OCR."""
    from .pipeline import exportar_documento

    dados = obter_config(config)
    try:
        pasta = exportar_documento(dados, id_documento)
    except ValueError as erro:
        typer.echo(f"ERRO: {erro}")
        raise typer.Exit(code=2) from erro
    typer.echo(f"Exportado em: {pasta}")


if __name__ == "__main__":
    app()
