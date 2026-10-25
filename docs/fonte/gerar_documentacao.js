// Gera docs/Documentacao_Final.docx a partir do conteúdo abaixo.
// Uso: npm install docx && node docs/fonte/gerar_documentacao.js
const fs = require("fs");
const path = require("path");
const {
  AlignmentType, BorderStyle, Document, Footer, HeadingLevel, ImageRun, LevelFormat, Packer,
  PageBreak, PageNumber, Paragraph, ShadingType, Table, TableCell, TableOfContents, TableRow,
  TextRun, WidthType,
} = require("docx");

const RAIZ = path.resolve(__dirname, "..");
const SAIDA = path.join(RAIZ, "Documentacao_Final.docx");

// A4 com margens ABNT (3 cm superior/esquerda, 2 cm inferior/direita)
const PAGINA = { width: 11906, height: 16838 };
const MARGEM = { top: 1701, left: 1701, bottom: 1134, right: 1134 };
const LARGURA = PAGINA.width - MARGEM.left - MARGEM.right; // 9071 DXA
const LARGURA_PX = 600;
const FONTE = "Arial";
const COR_TITULO = "1F3864";
const COR_CABECALHO = "D9E2F3";
const BORDA = { style: BorderStyle.SINGLE, size: 4, color: "8EA9DB" };

// --------------------------------------------------------------------------- helpers

function runs(texto, base = {}) {
  // **negrito** e `código` simples
  return texto.split(/(\*\*[^*]+\*\*|`[^`]+`)/).filter(Boolean).map((parte) => {
    if (parte.startsWith("**")) return new TextRun({ ...base, text: parte.slice(2, -2), bold: true });
    if (parte.startsWith("`")) return new TextRun({ ...base, text: parte.slice(1, -1), font: "Consolas", size: 20 });
    return new TextRun({ ...base, text: parte });
  });
}

const P = (texto, opts = {}) => new Paragraph({
  children: runs(texto), alignment: AlignmentType.JUSTIFIED, spacing: { after: 120, line: 360 }, ...opts,
});
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)], pageBreakBefore: true });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)] });
const item = (t, nivel = 0) => new Paragraph({
  children: runs(t), numbering: { reference: "marcadores", level: nivel }, spacing: { after: 60, line: 300 },
});
const num = (t, ref = "numeros") => new Paragraph({
  children: runs(t), numbering: { reference: ref, level: 0 }, spacing: { after: 60, line: 300 },
});
const codigo = (linhas) => linhas.map((l, i) => new Paragraph({
  children: [new TextRun({ text: l || " ", font: "Consolas", size: 18 })],
  shading: { type: ShadingType.CLEAR, color: "auto", fill: "F2F2F2" },
  spacing: { before: i === 0 ? 60 : 0, after: i === linhas.length - 1 ? 160 : 0 },
  indent: { left: 200, right: 200 },
}));
const legenda = (t) => new Paragraph({
  children: [new TextRun({ text: t, italics: true, size: 18, color: "555555" })],
  alignment: AlignmentType.CENTER, spacing: { after: 240 },
});
const fonte = (t) => new Paragraph({
  children: [new TextRun({ text: "Fonte: " + t, size: 18, color: "555555" })],
  alignment: AlignmentType.CENTER, spacing: { after: 240 },
});

function tamanhoPng(arquivo) {
  const b = fs.readFileSync(arquivo);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20), dados: b };
}

let numeroFigura = 0;
function figura(relativo, titulo, { largura = LARGURA_PX, alturaMax = 760 } = {}) {
  const { w, h, dados } = tamanhoPng(path.join(RAIZ, relativo));
  let lw = Math.min(largura, w);
  let lh = Math.round((h * lw) / w);
  if (lh > alturaMax) { lh = alturaMax; lw = Math.round((w * lh) / h); }
  numeroFigura += 1;
  return [
    new Paragraph({
      children: [new TextRun({ text: `Figura ${numeroFigura} — ${titulo}`, bold: true, size: 20 })],
      alignment: AlignmentType.CENTER, spacing: { before: 200, after: 80 }, keepNext: true,
    }),
    new Paragraph({
      children: [new ImageRun({ type: "png", data: dados, transformation: { width: lw, height: lh },
        altText: { title: titulo, description: titulo, name: path.basename(relativo) } })],
      alignment: AlignmentType.CENTER, keepNext: true,
    }),
    fonte("elaborado pelo autor (" + relativo.replace(/\\/g, "/") + ")."),
  ];
}

let numeroTabela = 0;
function tabela(titulo, cabecalho, linhas, pesos) {
  const total = pesos.reduce((a, b) => a + b, 0);
  const larguras = pesos.map((p) => Math.floor((p / total) * LARGURA));
  larguras[larguras.length - 1] += LARGURA - larguras.reduce((a, b) => a + b, 0);
  const celula = (texto, i, cab) => new TableCell({
    width: { size: larguras[i], type: WidthType.DXA },
    borders: { top: BORDA, bottom: BORDA, left: BORDA, right: BORDA },
    shading: cab ? { type: ShadingType.CLEAR, color: "auto", fill: COR_CABECALHO } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: String(texto).split("\n").map((linha) => new Paragraph({
      children: runs(linha, { size: 19, bold: cab || undefined }), spacing: { after: 20 },
    })),
  });
  numeroTabela += 1;
  return [
    new Paragraph({
      children: [new TextRun({ text: `Tabela ${numeroTabela} — ${titulo}`, bold: true, size: 20 })],
      alignment: AlignmentType.CENTER, spacing: { before: 200, after: 80 }, keepNext: true,
    }),
    new Table({
      width: { size: LARGURA, type: WidthType.DXA },
      columnWidths: larguras,
      rows: [
        new TableRow({ tableHeader: true, children: cabecalho.map((t, i) => celula(t, i, true)) }),
        ...linhas.map((l) => new TableRow({ cantSplit: true, children: l.map((t, i) => celula(t, i, false)) })),
      ],
    }),
    new Paragraph({ spacing: { after: 160 }, children: [] }),
  ];
}

// --------------------------------------------------------------------------- conteúdo

const AUTOR = "Bruno Pinheiro Dos Santos";
const TITULO = "Sistema de Gestão para Locadora de Veículos";
const VERSAO = "Versão 1.1";

const capa = [
  new Paragraph({ children: [new TextRun({ text: AUTOR.toUpperCase(), bold: true, size: 28 })],
    alignment: AlignmentType.CENTER, spacing: { after: 4200 } }),
  new Paragraph({ children: [new TextRun({ text: TITULO, bold: true, size: 40, color: COR_TITULO })],
    alignment: AlignmentType.CENTER, spacing: { after: 240 } }),
  new Paragraph({ children: [new TextRun({ text: "Documentação do Projeto de Software", size: 26 })],
    alignment: AlignmentType.CENTER, spacing: { after: 240 } }),
  new Paragraph({ children: [new TextRun({ text: VERSAO, size: 26 })],
    alignment: AlignmentType.CENTER, spacing: { after: 5200 } }),
  new Paragraph({ children: [new TextRun({ text: "São Paulo", size: 24 })], alignment: AlignmentType.CENTER }),
  new Paragraph({ children: [new TextRun({ text: "2026", size: 24 })], alignment: AlignmentType.CENTER }),
];

const historico = [
  new Paragraph({ children: [new TextRun({ text: "HISTÓRICO DE VERSÕES", bold: true, size: 26 })],
    alignment: AlignmentType.CENTER, spacing: { after: 240 }, pageBreakBefore: true }),
  ...tabela("Histórico de versões do documento", ["Versão", "Data", "Autor", "Descrição"], [
    ["0.1", "10/10/2026", AUTOR, "Visão geral, problemática, requisitos e protótipo de baixa fidelidade."],
    ["0.2", "10/10/2026", AUTOR, "Modelo de domínio, regras de negócio, casos de uso, diagramas e ADRs."],
    ["1.0", "11/10/2026", AUTOR, "Implementação concluída (UC01–UC05), protótipo de alta fidelidade, estratégia de testes e revisão final."],
    ["1.1", "25/10/2026", AUTOR, "Rodada de testes exploratórios e de sistema; 6 defeitos corrigidos; 83 testes e 99% de cobertura."],
  ], [1, 1.4, 2.6, 5]),
  new Paragraph({ children: [new TextRun({ text: "SUMÁRIO", bold: true, size: 26 })],
    alignment: AlignmentType.CENTER, spacing: { before: 400, after: 240 }, pageBreakBefore: true }),
  new TableOfContents("Sumário", { hyperlink: true, headingStyleRange: "1-3" }),
  P("Observação: caso o sumário apareça vazio, clique sobre ele com o botão direito e escolha “Atualizar campo” (Word) ou use Ferramentas → Atualizar → Índices (LibreOffice).", { alignment: AlignmentType.LEFT }),
];

// 1 ------------------------------------------------------------------------- visão geral
const RN = [
  ["RN01", "Cliente", "O cliente deve ter 21 anos ou mais na data da retirada.", "rules.validar_idade", "test_rn01_*"],
  ["RN02", "Cliente", "A CNH deve ser categoria B ou superior e estar válida até, no mínimo, a data de devolução prevista.", "rules.validar_cnh", "test_rn02_*"],
  ["RN03", "Cliente", "O CPF é único no sistema. Cliente inativo não pode reservar.", "Cliente.cpf (unique) · rules.validar_cliente_ativo", "test_rn03_*, test_cpf"],
  ["RN04", "Cliente", "Cliente com locação ATRASADA não pode abrir nova reserva.", "rules.validar_sem_atraso", "test_rn04_*"],
  ["RN05", "Veículo", "Só é ofertado veículo com status DISPONIVEL.", "operacoes.veiculos_disponiveis", "test_rn05_*"],
  ["RN06", "Veículo", "Um veículo não pode ter duas reservas ATIVA ou locações EM_ANDAMENTO com períodos sobrepostos.", "rules.ha_sobreposicao · operacoes._validar_veiculo", "SobreposicaoTests (8) · test_rn06_*"],
  ["RN07", "Veículo", "Veículo em MANUTENCAO ou INATIVO não aparece na busca de disponibilidade.", "operacoes.veiculos_disponiveis", "test_rn05_rn07_*"],
  ["RN08", "Reserva", "O período mínimo é de 1 diária e o máximo de 30 dias.", "rules.validar_periodo", "test_rn08_*"],
  ["RN09", "Reserva", "A data de retirada prevista deve ser igual ou posterior ao momento da reserva.", "rules.validar_periodo", "test_rn09_*"],
  ["RN10", "Reserva", "A devolução prevista deve ser posterior à retirada prevista.", "rules.validar_periodo · BuscaDisponibilidadeForm", "test_rn10_*"],
  ["RN11", "Reserva", "O cancelamento é livre até 24 horas antes da retirada prevista. Depois disso, aplica-se multa de 20% sobre o valor estimado.", "rules.cancelamento_com_multa · services.multa_cancelamento", "test_rn11_*"],
  ["RN12", "Reserva", "Reserva não retirada até 4 horas após a hora prevista passa a EXPIRADA e libera o veículo.", "rules.reserva_expirada · operacoes.atualizar_status_temporais", "test_rn12_*"],
  ["RN13", "Retirada", "Só uma reserva com status ATIVA pode ser convertida em locação.", "rules.validar_reserva_convertivel", "test_rn13_*"],
  ["RN14", "Retirada", "A retirada exige registro de quilometragem e nível de combustível de saída.", "rules.validar_dados_saida · RetiradaForm", "test_rn14_*"],
  ["RN15", "Retirada", "Na retirada, o veículo passa a LOCADO, a reserva passa a CONVERTIDA e a caução é registrada.", "operacoes.registrar_retirada", "test_rn15_*"],
  ["RN16", "Devolução", "A quilometragem de retorno deve ser maior ou igual à de saída.", "rules.validar_km_retorno", "test_rn16_*"],
  ["RN17", "Devolução", "Devolução após a tolerância de 60 minutos gera multa, conforme as regras de cálculo.", "services.diarias_de_atraso · services.valor_multa", "DiariasDeAtrasoTests · test_atrasada_*"],
  ["RN18", "Devolução", "Na devolução o veículo volta a DISPONIVEL. Se houver avaria registrada, vai para MANUTENCAO.", "operacoes.registrar_devolucao", "test_rn18_*"],
  ["RN19", "Devolução", "Locação FINALIZADA é imutável: nenhum campo pode ser alterado depois do fechamento.", "Locacao.save · operacoes.registrar_devolucao", "test_rn19_*"],
];

const visaoGeral = [
  H1("1 VISÃO GERAL DO PROJETO"),
  H2("1.1 Descrição Executiva"),
  P("O **Sistema de Gestão para Locadora de Veículos** é uma aplicação web que controla o ciclo completo de uma locação: o cliente **reserva** um veículo para um período, **retira** na loja, **devolve**, e o sistema **apura o valor final** — diárias, multa por atraso e taxa de combustível — de forma automática, auditável e consistente."),
  P("A solução foi construída como um monólito em **Python 3 e Django 5.2 LTS**, com banco **SQLite** e interface em **Bootstrap 5**. O núcleo do domínio — as cinco fórmulas de cálculo e as dezenove regras de negócio (RN01 a RN19) — foi isolado em funções puras, sem acesso a banco, o que torna as regras fáceis de explicar, testar e manter."),
  P("O sistema é operado pelos funcionários da locadora (atendentes e gerentes), que acessam com login e senha. O recorte entregue cobre cinco casos de uso completos: manter veículo (UC01), manter cliente (UC02), consultar disponibilidade e reservar (UC03), registrar retirada (UC04) e registrar devolução e apurar valores (UC05). A suíte de 83 testes automatizados (99% de cobertura de código) e um teste de sistema no navegador comprovam o comportamento, inclusive o exemplo numérico de referência do projeto (total de R$ 690,00)."),
  ...tabela("Resumo do projeto", ["Item", "Descrição"], [
    ["Produto", TITULO],
    ["Tipo", "Aplicação web (navegador de computador, tablet ou smartphone)"],
    ["Usuários", "Atendentes e gerentes da locadora"],
    ["Stack", "Python 3.12+ · Django 5.2 LTS · SQLite · Bootstrap 5 · Mermaid"],
    ["Casos de uso", "UC01 a UC05 (ciclo reserva → retirada → devolução)"],
    ["Regras de negócio", "19 (RN01 a RN19), todas implementadas e rastreáveis até teste"],
    ["Testes", "83 testes automatizados (unidade, integração e interface), 99% de cobertura de código, mais teste de sistema no navegador"],
    ["Repositório", "github.com/bruno011203/projeto-da-loca-o-de-carros"],
  ], [1, 3]),

  H2("1.2 Objetivos e Escopo"),
  H3("1.2.1 Objetivo geral"),
  P("Informatizar a operação de aluguel de veículos da locadora, substituindo controles manuais por um sistema que garanta disponibilidade correta da frota, aplique as regras comerciais de forma uniforme e calcule automaticamente o valor de cada locação."),
  H3("1.2.2 Objetivos específicos"),
  item("Manter o cadastro de veículos, categorias de preço e clientes, com validações de CPF, placa, chassi e CNH."),
  item("Permitir consultar a disponibilidade da frota para um período, impedindo reservas sobrepostas para o mesmo veículo (RN06)."),
  item("Registrar reservas com código único, valor estimado e política de cancelamento (RN11) e expiração (RN12)."),
  item("Registrar a retirada com quilometragem, nível de combustível, caução e congelamento do preço da diária (snapshot de preço)."),
  item("Registrar a devolução e apurar automaticamente diárias, multa por atraso, taxa de combustível e destino da caução."),
  item("Oferecer um painel com os números do dia: veículos livres, locações em andamento e atrasadas, retiradas e devoluções previstas."),
  H3("1.2.3 Dentro do escopo"),
  ...tabela("Casos de uso dentro do escopo e regras que cobrem", ["Caso de uso", "Regras cobertas"], [
    ["UC01 — Manter veículo", "RN05, RN07"],
    ["UC02 — Manter cliente", "RN01, RN02, RN03"],
    ["UC03 — Consultar disponibilidade e reservar", "RN04, RN06, RN08, RN09, RN10, RN11, RN12"],
    ["UC04 — Registrar retirada", "RN13, RN14, RN15"],
    ["UC05 — Registrar devolução e apurar valores", "RN16, RN17, RN18, RN19"],
  ], [3, 2]),
  H3("1.2.4 Fora do escopo (trabalho futuro)"),
  P("O recorte preserva o núcleo do domínio — o ciclo reserva, retirada e devolução — e exclui o que é periférico. Os itens abaixo estão documentados no Apêndice A como trabalho futuro:"),
  item("Pagamento e integração com gateway financeiro."),
  item("Permissões diferenciadas por perfil (o perfil do Funcionário está modelado; hoje todo funcionário autenticado opera o sistema e apenas o gerente acessa o painel administrativo)."),
  item("Registro de avarias com fotos (hoje a avaria é registrada com descrição textual)."),
  item("Relatórios gerenciais avançados (o painel do dia foi entregue)."),
  item("Operação multi-filial e notificações por e-mail."),
  item("API REST."),

  H2("1.3 Problemática"),
  P("Locadoras de pequeno e médio porte frequentemente controlam reservas em planilhas, agendas ou sistemas genéricos. Esse modelo gera problemas recorrentes:"),
  item("**Overbooking:** o mesmo carro é prometido a dois clientes em períodos que se cruzam, porque a verificação considera apenas se o carro “está no pátio agora”, e não a sobreposição de períodos futuros."),
  item("**Cobrança inconsistente:** cada atendente calcula atraso, frações de diária e combustível de um jeito, gerando discussões com clientes e perda de receita."),
  item("**Preço retroativo:** quando a tabela de preços muda, contratos antigos em planilha são recalculados com o valor novo."),
  item("**Riscos legais e operacionais:** carros entregues a condutores sem idade mínima, com CNH vencida ou de categoria inadequada, ou a clientes que ainda não devolveram outro veículo."),
  item("**Falta de visibilidade:** o gerente não sabe, de imediato, quantos carros estão livres, quantas locações estão atrasadas e quanto foi faturado no dia."),
  P("O sistema resolve esses pontos ao separar **reserva** (compromisso sobre um período futuro, que bloqueia o veículo e pode ser cancelado) de **locação** (o contrato em execução, que nasce na retirada e termina na devolução), aplicar as regras de negócio no momento certo de cada transição e calcular os valores com fórmulas únicas, testadas e versionadas."),

  H2("1.4 Regras de Negócio"),
  H3("1.4.1 Glossário do domínio"),
  ...tabela("Termos do domínio", ["Termo", "Significado no sistema"], [
    ["Categoria", "Faixa de veículos com a mesma diária (Econômico, Intermediário, SUV, Executivo). O preço pertence à categoria, não ao veículo."],
    ["Diária", "Bloco de 24 horas corridas contado a partir da hora da retirada."],
    ["Disponibilidade", "Veículo com status DISPONIVEL e sem reserva ou locação sobreposta ao período pedido."],
    ["Caução", "Valor retido na retirada e devolvido se não houver avaria nem pendência."],
    ["Tolerância", "Minutos de atraso na devolução que não geram multa. Padrão: 60 minutos."],
    ["Diária extra", "Cada bloco de 24 h iniciado além do período contratado."],
    ["Snapshot de preço", "Cópia do valor da diária da categoria para a locação no momento da retirada."],
  ], [1, 3]),
  H3("1.4.2 Regras de negócio e rastreabilidade"),
  P("As dezenove regras abaixo são verificáveis em código e rastreáveis até o requisito funcional, o caso de uso e o teste automatizado que as comprova. As mensagens de erro exibidas ao usuário trazem o código da regra (por exemplo, “RN06: o veículo já possui reserva ou locação nesse período.”)."),
  ...tabela("Regras de negócio RN01–RN19", ["Código", "Área", "Regra", "Implementação", "Teste"],
    RN, [0.8, 1, 3.6, 2.4, 1.8]),
  P("**RN06 é a regra mais importante do sistema.** Ela não é um simples `status == DISPONIVEL`: é uma verificação de sobreposição de intervalos. Há conflito quando `novaRetirada < devolucaoExistente` **e** `novaDevolucao > retiradaExistente`. Períodos que apenas se encostam (um termina exatamente quando o outro começa) não conflitam. A função `ha_sobreposicao` tem oito testes unitários dedicados: sobreposição total, período contido, parcial no início, parcial no fim, encaixe exato antes, encaixe exato depois, sem conflito e lista vazia."),
  H3("1.4.3 Regras de cálculo"),
  P("As cinco fórmulas são funções puras em `locacao/services.py`. Todos os valores monetários usam `Decimal` com duas casas e arredondamento **HALF_UP** — nunca ponto flutuante para dinheiro."),
  ...tabela("Fórmulas de cálculo", ["Fórmula", "Expressão", "Função"], [
    ["Diárias contratadas", "D = ⌈(devolucaoPrevista − retirada) / 24h⌉ (mínimo 1)", "diarias_contratadas"],
    ["Valor previsto", "Vprevisto = D × valorDiariaAplicado", "valor_previsto"],
    ["Diárias de atraso", "Datraso = max(0, ⌈(devolucaoReal − devolucaoPrevista − 60 min) / 24h⌉)", "diarias_de_atraso"],
    ["Multa por atraso", "M = Datraso × valorDiariaAplicado × 1,5", "valor_multa"],
    ["Taxa de combustível", "C = max(0, qsaída − qretorno) × valorTanqueCheio / 4", "taxa_combustivel"],
    ["Total", "Vtotal = Vprevisto + M + C (caução tratada à parte)", "valor_total"],
    ["Multa de cancelamento", "20% × valorEstimado, se faltar menos de 24 h (RN11)", "multa_cancelamento"],
  ], [1.4, 3.2, 1.4]),
  H3("1.4.4 Exemplo numérico"),
  P("Categoria Econômico, diária R$ 120,00, caução R$ 500,00, tanque cheio R$ 300,00. Este exemplo é reproduzido literalmente pelo teste `ExemploNumericoDoDocumentoTests` e pelos dados de exemplo (`python manage.py seed`, locação nº 1)."),
  ...tabela("Exemplo numérico de apuração", ["Dado", "Valor"], [
    ["Retirada", "10/10/2026 09:00, tanque CHEIO, 32.100 km"],
    ["Devolução prevista", "13/10/2026 09:00"],
    ["Devolução real", "13/10/2026 14:00, tanque METADE, 32.740 km"],
    ["Diárias contratadas", "3 → R$ 360,00"],
    ["Atraso", "5 h, menos 1 h de tolerância = 4 h → 1 diária extra"],
    ["Multa", "1 × 120 × 1,5 = R$ 180,00"],
    ["Combustível", "2 quartos × R$ 75,00 = R$ 150,00"],
    ["Total", "**R$ 690,00** (caução de R$ 500,00 devolvida)"],
  ], [1, 2.5]),

  H2("1.5 Métricas e Cronograma"),
  H3("1.5.1 Métricas do projeto"),
  ...tabela("Métricas de produto e de qualidade", ["Métrica", "Meta", "Resultado"], [
    ["Casos de uso entregues por inteiro", "5 de 5", "5 de 5 (UC01–UC05)"],
    ["Regras de negócio implementadas", "19 de 19", "19 de 19, cada uma com teste"],
    ["Fórmulas de cálculo testadas", "5 de 5", "5 de 5 + exemplo numérico completo"],
    ["Testes automatizados passando", "100%", "83 de 83 (≈ 13 s), também em ordem aleatória"],
    ["Cobertura de código (coverage.py)", "≥ 90%", "99% (views, forms, admin, regras e fórmulas)"],
    ["Teste de sistema no navegador (Chromium)", "100% dos passos", "25 de 25 passos, sem erro de JavaScript nem HTTP 500"],
    ["Defeitos conhecidos em aberto", "0", "0 — 6 defeitos encontrados nos testes foram corrigidos (Apêndice F)"],
    ["Overbooking (reservas sobrepostas aceitas)", "0", "0 — recusado pela regra RN06 e por lock de linha"],
    ["Tempo para apurar uma devolução", "< 1 minuto", "Cálculo instantâneo, com prévia antes de confirmar"],
    ["Tempo de resposta das telas (ambiente local)", "< 1 s", "Atendido"],
    ["Linhas de código de domínio (rules + services + operacoes)", "—", "≈ 420"],
  ], [3, 1.4, 2.6]),
  H3("1.5.2 Cronograma (6 dias)"),
  ...tabela("Cronograma de execução", ["Dia", "Entrega", "Situação"], [
    ["1", "Visão geral, problemática, requisitos funcionais e não-funcionais, protótipo de baixa fidelidade; projeto Django de pé, enums e modelos.", "Concluído"],
    ["2", "Modelo de domínio, diagrama de classes, casos de uso, diagrama de sequência da devolução, ADRs; services.py e rules.py com testes.", "Concluído"],
    ["3", "Entidades, persistência, CRUD de veículo e cliente (UC01, UC02) pelo admin e por telas próprias.", "Concluído"],
    ["4", "Disponibilidade e reserva (UC03) — RN06 e consulta de períodos sobrepostos.", "Concluído"],
    ["5", "Retirada e devolução com cálculo (UC04, UC05), painel do dia e acabamento em Bootstrap.", "Concluído"],
    ["6", "Testes de integração, protótipo de alta fidelidade (capturas), fechamento do documento.", "Concluído"],
  ], [0.6, 5, 1.2]),
];

// 2 ------------------------------------------------------------------------- arquitetura
const ADRS = [
  ["ADR-001", "Django monolítico com templates", "Prazo de seis dias e um único desenvolvedor. FastAPI + React exigiria duas bases de código, autenticação manual, CORS e build de front-end.",
    "Usar Django 5.2 LTS, um único projeto e um único app (`locacao`), com templates e Bootstrap por CDN.",
    "ORM, migrations, admin, formulários, autenticação e testes no mesmo pacote. O Django Admin entrega o CRUD de UC01/UC02 praticamente pronto. Em troca, não há API pública (fica como trabalho futuro)."],
  ["ADR-002", "SQLite como banco de dados", "O sistema roda em uma loja, com poucos usuários simultâneos, e precisa de instalação simples.",
    "Usar SQLite em desenvolvimento e na entrega acadêmica.",
    "Zero configuração. Para produção com vários atendentes, trocar para PostgreSQL é editar `DATABASES` e rodar as migrations; o código não muda."],
  ["ADR-003", "Snapshot de preço na locação", "O preço pertence à categoria e pode mudar a qualquer momento.",
    "Copiar `valor_diaria` e `valor_caucao` da categoria para a locação no momento da retirada (`valor_diaria_aplicado`).",
    "Locações antigas nunca são reescritas quando a tabela de preços muda. Coberto por `test_snapshot_de_preco`."],
  ["ADR-004", "Devolução é operação, não entidade", "A devolução não tem ciclo de vida próprio: ela apenas fecha a locação.",
    "Modelar a devolução como a operação `registrar_devolucao`, que preenche os campos de retorno da Locação e a torna FINALIZADA.",
    "Modelo com sete entidades, sem tabela redundante. Os campos de retorno ficam nulos enquanto a locação está aberta."],
  ["ADR-005", "Regras e fórmulas como funções puras", "As regras são o trecho que a banca pede para explicar linha a linha e o que mais precisa de testes.",
    "Isolar `services.py` (fórmulas) e `rules.py` (RN) dos models; elas recebem números e datas e devolvem números, booleanos ou lançam `RegraNegocioError`. `operacoes.py` orquestra banco + regras em transações.",
    "Testes unitários rodam em milissegundos, sem banco. A interface e o admin reutilizam as mesmas regras."],
  ["ADR-006", "ATRASADA e EXPIRADA por avaliação preguiçosa", "Os estados ATRASADA (RN17) e EXPIRADA (RN12) são disparados pelo tempo, não por ação do usuário.",
    "Em vez de um agendador (cron/Celery), a função `atualizar_status_temporais` é chamada no início das telas e operações e atualiza em lote o que venceu.",
    "Mais simples, sem processo extra. Desvantagem: o status no banco só muda quando alguém usa o sistema — aceitável para uma loja em funcionamento."],
  ["ADR-007", "Funcionário ligado ao User do Django", "O modelo prevê login e senhaHash no Funcionário.",
    "Usar `OneToOneField` com o `User` do Django; login, hash de senha (PBKDF2) e sessão vêm prontos.",
    "Nenhuma criptografia caseira. O campo `senhaHash` do modelo conceitual é atendido pelo `User.password`."],
  ["ADR-008", "Concorrência na reserva", "Dois atendentes podem tentar reservar o mesmo carro ao mesmo tempo.",
    "Criar reserva e retirada dentro de `transaction.atomic`, relendo o veículo com `select_for_update` antes de verificar a sobreposição.",
    "Elimina a condição de corrida em bancos com lock de linha (PostgreSQL); no SQLite as escritas já são serializadas."],
];

const arquitetura = [
  H1("2 ARQUITETURA DO SISTEMA"),
  P("O sistema segue a arquitetura em camadas de um monólito Django (padrão MTV — Model, Template, View), com uma camada de domínio explícita. A Figura abaixo mostra o caminho de uma requisição, do navegador ao banco."),
  ...figura("diagramas/06_arquitetura.png", "Arquitetura em camadas", { largura: 470 }),
  H2("2.1 Componentes Principais"),
  ...tabela("Componentes do sistema", ["Componente", "Arquivo(s)", "Responsabilidade"], [
    ["Configuração", "config/settings.py, config/urls.py", "Idioma pt-br, fuso America/Sao_Paulo, USE_TZ, apps instalados, login e rotas raiz."],
    ["Enumerações", "locacao/enums.py", "StatusVeiculo, StatusReserva, StatusLocacao, CategoriaCNH, NivelCombustivel (com valor em quartos) e PerfilUsuario como TextChoices."],
    ["Modelos (ORM)", "locacao/models.py, validators.py", "As 7 entidades, a CNH como objeto de valor, validação de CPF/placa/chassi e a imutabilidade da locação finalizada (RN19)."],
    ["Fórmulas", "locacao/services.py", "As 5 fórmulas de cálculo e o extrato da devolução — funções puras com Decimal HALF_UP."],
    ["Regras", "locacao/rules.py", "Validações RN01–RN19 e a função ha_sobreposicao (RN06) — funções puras que lançam RegraNegocioError com o código da regra."],
    ["Operações (casos de uso)", "locacao/operacoes.py", "UC03–UC05: disponibilidade, criar/cancelar reserva, retirada (com reserva ou de balcão), devolução; transações e locks."],
    ["Formulários", "locacao/forms.py", "Validação de entrada das telas (datas, km, combustível, CPF formatado) e estilo Bootstrap."],
    ["Views e rotas", "locacao/views.py, urls.py", "Telas protegidas por login; traduzem RegraNegocioError em mensagens ao usuário."],
    ["Templates", "locacao/templates/", "Interface responsiva com Bootstrap 5 e Bootstrap Icons via CDN."],
    ["Administração", "locacao/admin.py", "UC01 e UC02 pelo Django Admin, com busca e filtros; reservas e locações em modo somente leitura."],
    ["Carga de dados", "management/commands/seed.py", "Categorias, 10 veículos, clientes, funcionários, reservas e locações de exemplo."],
    ["Testes", "locacao/tests/", "83 testes em três níveis (fórmulas, regras, integração e interface)."],
  ], [1.5, 2, 4]),
  H2("2.2 Decisões Arquiteturais (ADR)"),
  P("Cada decisão segue o formato contexto → decisão → consequências. Todas têm status **Aceita**."),
  ...ADRS.flatMap(([id, titulo, contexto, decisao, consequencias]) => [
    H3(`${id} — ${titulo}`),
    ...tabela(`${id}`, ["Campo", "Descrição"], [
      ["Status", "Aceita"], ["Contexto", contexto], ["Decisão", decisao], ["Consequências", consequencias],
    ], [1, 4]),
  ]),
];

// 3 ------------------------------------------------------------------------- especificação técnica
const RF = [
  ["RF01", "Autenticar funcionário com login e senha; todas as telas exigem sessão ativa.", "—", "Todos"],
  ["RF02", "Cadastrar, editar, buscar e filtrar veículos (placa, chassi, marca, modelo, ano, cor, km, categoria, status).", "UC01", "RN05, RN07"],
  ["RF03", "Manter categorias com diária, caução e valor do tanque cheio (admin).", "UC01", "—"],
  ["RF04", "Cadastrar, editar, buscar e inativar clientes, com CNH embutida.", "UC02", "RN01, RN02, RN03"],
  ["RF05", "Consultar veículos disponíveis por período e categoria, exibindo o valor estimado.", "UC03", "RN05, RN06, RN07"],
  ["RF06", "Criar reserva com código único e valor estimado.", "UC03", "RN01–RN04, RN06, RN08–RN10"],
  ["RF07", "Cancelar reserva, calculando multa quando tardia.", "UC03", "RN11"],
  ["RF08", "Expirar automaticamente reservas não retiradas.", "UC03", "RN12"],
  ["RF09", "Registrar retirada a partir de reserva ATIVA, com km, combustível, caução e snapshot de preço.", "UC04", "RN13, RN14, RN15"],
  ["RF10", "Registrar locação de balcão (sem reserva prévia).", "UC04", "RN01–RN06, RN14, RN15"],
  ["RF11", "Exibir prévia do extrato da devolução antes de confirmar.", "UC05", "RN16, RN17"],
  ["RF12", "Registrar devolução, apurar valores, destinar a caução e liberar ou enviar o veículo à manutenção.", "UC05", "RN16–RN19"],
  ["RF13", "Marcar locações como ATRASADA após a tolerância.", "UC05", "RN17"],
  ["RF14", "Listar reservas e locações com filtro por status e consultar o detalhe de cada uma.", "UC03–UC05", "—"],
  ["RF15", "Exibir painel do dia (veículos livres, em andamento, atrasadas, manutenção, faturado hoje, retiradas e devoluções do dia).", "—", "—"],
  ["RF16", "Exibir o histórico de reservas e locações de cada cliente.", "UC02", "—"],
];

const RNF = [
  ["RNF01", "Usabilidade", "Interface em português do Brasil, datas dd/mm/aaaa, moeda R$ 1.234,56; mensagens de erro citam a regra violada.", "Templates + filtros moeda/data"],
  ["RNF02", "Responsividade", "Telas utilizáveis em telas a partir de 360 px de largura (smartphone).", "Grid e tabelas responsivas do Bootstrap 5"],
  ["RNF03", "Segurança", "Senhas com hash PBKDF2, proteção CSRF em todos os formulários, sessão obrigatória, admin restrito ao gerente.", "django.contrib.auth, CsrfViewMiddleware, login_required"],
  ["RNF04", "Integridade de dados", "Valores monetários em Decimal(10,2) com HALF_UP; CPF, placa, chassi e código de reserva únicos; chaves estrangeiras protegidas (PROTECT).", "models.py, services.py"],
  ["RNF05", "Consistência transacional", "Reserva, retirada e devolução são atômicas; o veículo é bloqueado (select_for_update) durante a verificação de disponibilidade.", "operacoes.py"],
  ["RNF06", "Desempenho", "Telas respondem em menos de 1 s com a frota de exemplo; consultas usam select_related e filtros no banco.", "views.py"],
  ["RNF07", "Manutenibilidade", "Regras e fórmulas isoladas em funções puras, código em português seguindo PEP 8, um único app.", "rules.py, services.py"],
  ["RNF08", "Testabilidade", "Cada RN e cada fórmula possui ao menos um teste automatizado; a suíte roda com um comando.", "python manage.py test"],
  ["RNF09", "Portabilidade", "Roda em Windows, Linux e macOS com Python 3.12+; troca para PostgreSQL apenas por configuração.", "settings.DATABASES"],
  ["RNF10", "Fuso horário", "Datas armazenadas em UTC e exibidas em America/Sao_Paulo.", "USE_TZ = True"],
];

const UCS = [
  ["UC01 — Manter veículo", "Atendente / Gerente", "Funcionário autenticado; categorias cadastradas.",
    ["Acessa Veículos e escolhe “Novo veículo” ou “Editar”.", "Informa placa, chassi, marca, modelo, ano, cor, categoria, km e status.", "O sistema valida formato e unicidade de placa e chassi, ano e km não decrescente.", "O sistema grava e volta à lista, que pode ser filtrada por status e pesquisada."],
    "Placa ou chassi inválido/duplicado: a tela mostra o erro no campo. Veículo LOCADO: o status fica bloqueado até a devolução.", "RN05, RN07"],
  ["UC02 — Manter cliente", "Atendente / Gerente", "Funcionário autenticado.",
    ["Acessa Clientes e escolhe “Novo cliente” ou “Editar”.", "Informa nome, CPF, nascimento, contato, endereço e dados da CNH.", "O sistema valida o CPF (dígitos verificadores) e sua unicidade.", "O sistema grava e mostra o detalhe do cliente com idade, CNH e histórico."],
    "CPF inválido ou já cadastrado: erro no campo. Cliente pode ser marcado como inativo (RN03).", "RN01, RN02, RN03"],
  ["UC03 — Consultar disponibilidade e reservar", "Atendente", "Funcionário autenticado; cliente cadastrado.",
    ["Informa retirada, devolução e, opcionalmente, categoria.", "O sistema lista os veículos DISPONÍVEIS sem reserva sobreposta, com valor estimado.", "O atendente escolhe o veículo e o cliente.", "O sistema valida período, cliente e sobreposição e cria a reserva ATIVA com código.", "O sistema exibe a confirmação com o código."],
    "Regra violada (RN01–RN10): mensagem com o código da regra e nada é gravado. Extensão “Cancelar reserva”: livre até 24 h antes; depois, multa de 20% (RN11). Sem retirada 4 h após o horário, a reserva expira (RN12).", "RN04, RN06, RN08–RN12"],
  ["UC04 — Registrar retirada", "Atendente", "Reserva ATIVA (ou locação de balcão).",
    ["Abre a reserva e escolhe “Registrar retirada”.", "Informa km e nível de combustível de saída.", "O sistema revalida cliente e veículo, copia a diária e a caução da categoria.", "O veículo passa a LOCADO, a reserva a CONVERTIDA e nasce a locação EM_ANDAMENTO com o atendente logado."],
    "Reserva não ATIVA: RN13. Km ou combustível ausente, ou km menor que o do veículo: RN14. Fluxo alternativo: locação de balcão, sem reserva prévia.", "RN13, RN14, RN15"],
  ["UC05 — Registrar devolução e apurar valores", "Atendente", "Locação EM_ANDAMENTO ou ATRASADA.",
    ["Abre a locação e escolhe “Registrar devolução”.", "Informa data/hora, km, combustível de retorno e se houve avaria.", "O sistema calcula e exibe o extrato (include “Calcular extrato”).", "O atendente confirma.", "O sistema grava os valores, finaliza a locação e libera o veículo (ou envia à manutenção se houve avaria)."],
    "Km de retorno menor que o de saída: RN16. Locação já finalizada: RN19, nenhuma alteração. Avaria: caução retida e veículo em MANUTENCAO (RN18).", "RN16–RN19"],
];

const especificacao = [
  H1("3 ESPECIFICAÇÃO TÉCNICA"),
  H2("3.1 Requisitos Funcionais"),
  ...tabela("Requisitos funcionais", ["ID", "Descrição", "Caso de uso", "Regras"], RF, [0.7, 4.6, 1.1, 1.6]),
  H2("3.2 Requisitos Não-Funcionais"),
  ...tabela("Requisitos não-funcionais", ["ID", "Categoria", "Requisito", "Como é atendido"], RNF, [0.7, 1.3, 3.6, 2.2]),
  H2("3.3 Protótipo de Baixa Fidelidade e Alta Fidelidade"),
  H3("3.3.1 Baixa fidelidade"),
  P("Os wireframes abaixo foram desenhados antes da implementação para validar o fluxo das quatro telas centrais (busca, reserva, retirada e devolução) e do painel. Usam apenas tons de cinza, caixas e marcações das regras envolvidas em cada tela."),
  ...figura("prototipos/baixa_01_painel.png", "Wireframe — painel do dia"),
  ...figura("prototipos/baixa_02_busca_disponibilidade.png", "Wireframe — consulta de disponibilidade (UC03)"),
  ...figura("prototipos/baixa_03_reserva.png", "Wireframe — nova reserva e confirmação (UC03)"),
  ...figura("prototipos/baixa_04_retirada.png", "Wireframe — registro de retirada (UC04)"),
  ...figura("prototipos/baixa_05_devolucao.png", "Wireframe — devolução e extrato (UC05)"),
  H3("3.3.2 Alta fidelidade"),
  P("O protótipo de alta fidelidade corresponde às telas reais do sistema, capturadas com os dados de exemplo do comando `seed`. A identidade visual usa Bootstrap 5: barra de navegação escura, cartões brancos sobre fundo cinza-claro e selos coloridos por status (verde = disponível/finalizada, azul = ativa/em andamento, amarelo = manutenção, vermelho = atrasada)."),
  ...figura("prototipos/alta_01_login.png", "Tela de login"),
  ...figura("prototipos/alta_02_painel.png", "Painel do dia"),
  ...figura("prototipos/alta_03_disponibilidade.png", "Consulta de disponibilidade com resultados"),
  ...figura("prototipos/alta_04_reserva_nova.png", "Nova reserva"),
  ...figura("prototipos/alta_05_reservas.png", "Lista de reservas com filtro por status"),
  ...figura("prototipos/alta_06_retirada.png", "Registro de retirada"),
  ...figura("prototipos/alta_07_locacoes.png", "Lista de locações"),
  ...figura("prototipos/alta_08_devolucao_extrato.png", "Devolução com extrato calculado (locação atrasada)"),
  ...figura("prototipos/alta_09_locacao_finalizada.png", "Locação finalizada — exemplo numérico de R$ 690,00"),
  ...figura("prototipos/alta_10_veiculos.png", "Frota com filtro por status"),
  ...figura("prototipos/alta_11_clientes.png", "Clientes"),
  ...figura("prototipos/alta_12_veiculo_form.png", "Cadastro de veículo"),

  H2("3.4 Arquitetura do Sistema"),
  P("A aplicação é um monólito Django organizado em camadas (ver também a seção 2 e o ADR-001):"),
  num("**Apresentação** — templates Django com Bootstrap 5, servidos pelas views; o navegador não executa regras de negócio.", "camadas"),
  num("**Controle** — `urls.py` e `views.py` recebem a requisição, exigem login, validam a entrada com `forms.py` e chamam as operações.", "camadas"),
  num("**Aplicação** — `operacoes.py` implementa os casos de uso UC03–UC05 dentro de transações.", "camadas"),
  num("**Domínio** — `rules.py` e `services.py`, funções puras sem dependência de banco.", "camadas"),
  num("**Persistência** — `models.py` (ORM do Django) sobre SQLite, com migrations versionadas.", "camadas"),
  P("O Django Admin é um segundo ponto de entrada, usado pelo gerente para manter categorias, veículos, clientes e funcionários (UC01/UC02). O modelo físico do banco está no Apêndice B."),

  H2("3.5 Modelo do Domínio"),
  P("Sete entidades bastam. Reserva e Locação são o centro: a Reserva é o único ponto em que Cliente e Veículo se encontram antes da retirada; a Locação herda esse par e acrescenta o atendente. A associação entre Reserva e Locação é 0..1 para 0..1 — nem toda reserva vira locação (pode ser cancelada ou expirar) e uma locação de balcão pode nascer sem reserva. A CNH é composição: não existe fora do Cliente."),
  ...figura("diagramas/01_modelo_dominio.png", "Modelo de domínio — 7 entidades, 8 associações"),
  ...tabela("Entidades do domínio", ["Entidade", "Atributos principais", "Papel"], [
    ["Cliente", "id, nome, cpf, email, telefone, dataNascimento, endereco, ativo, cnh", "Quem aluga. CPF é único."],
    ["CNH", "numero, categoria (A–E), validade", "Objeto de valor embutido no Cliente (colunas cnh_*), não é tabela própria."],
    ["Categoria", "id, nome, valorDiaria, valorCaucao, valorTanqueCheio, descricao", "Onde mora o preço."],
    ["Veiculo", "id, placa, chassi, marca, modelo, anoFabricacao, cor, kmAtual, status, categoria", "O bem locado. Placa e chassi únicos."],
    ["Reserva", "id, codigo, cliente, veiculo, retiradaPrevista, devolucaoPrevista, valorEstimado, status", "Compromisso sobre um período futuro."],
    ["Locacao", "id, reserva, cliente, veiculo, atendente, dataRetirada, devolucaoPrevista, devolucaoReal, kmSaida, kmRetorno, combustivelSaida, combustivelRetorno, valorDiariaAplicado, valorCaucao, valorMulta, valorTotal, avaria, status", "O contrato em execução."],
    ["Funcionario", "id, nome, matricula, login (User), perfil", "Quem opera o sistema."],
  ], [1.2, 4.2, 2]),
  ...tabela("Enumerações do domínio", ["Enum", "Valores"], [
    ["StatusVeiculo", "DISPONIVEL · LOCADO · MANUTENCAO · INATIVO"],
    ["StatusReserva", "ATIVA · CONVERTIDA · CANCELADA · EXPIRADA"],
    ["StatusLocacao", "EM_ANDAMENTO · FINALIZADA · ATRASADA"],
    ["CategoriaCNH", "A · B · C · D · E"],
    ["NivelCombustivel", "VAZIO (0) · UM_QUARTO (1) · METADE (2) · TRES_QUARTOS (3) · CHEIO (4)"],
    ["PerfilUsuario", "ATENDENTE · GERENTE"],
  ], [1.3, 4]),
  H3("3.5.1 Ciclo de vida"),
  P("Três estados pertencem à Reserva (ATIVA, CANCELADA, EXPIRADA) e três à Locação (EM_ANDAMENTO, ATRASADA, FINALIZADA). A retirada é a fronteira: a reserva passa a CONVERTIDA e nasce uma locação EM_ANDAMENTO. ATRASADA não é um beco sem saída — é EM_ANDAMENTO com multa acumulando, disparada pelo tempo (ADR-006). Todo estado terminal devolve o veículo a DISPONIVEL, exceto quando há avaria, caso em que ele vai a MANUTENCAO (RN18)."),
  ...figura("diagramas/05_ciclo_de_vida.png", "Máquina de estados — 6 estados, 6 transições"),

  H2("3.6 Diagramas de Caso de Uso"),
  ...figura("diagramas/03_casos_de_uso.png", "Diagrama de casos de uso", { largura: 520 }),
  P("O ator principal é o **Atendente**. O **Gerente** herda todos os casos de uso do atendente e, adicionalmente, acessa o Django Admin. A especificação de cada caso de uso segue."),
  ...UCS.flatMap(([nome, ator, pre, fluxo, alt, regras]) => [
    H3(nome),
    ...tabela(nome, ["Campo", "Descrição"], [
      ["Ator", ator], ["Pré-condição", pre],
      ["Fluxo principal", fluxo.map((f, i) => `${i + 1}. ${f}`).join("\n")],
      ["Fluxos alternativos / exceções", alt], ["Regras", regras],
    ], [1.3, 4.5]),
  ]),

  H2("3.7 Diagrama de Classes"),
  P("O diagrama de classes usa a notação do modelo conceitual (tipos Long, String, BigDecimal, LocalDateTime). Na implementação Django eles correspondem a AutoField, CharField, DecimalField(10,2) e DateTimeField com fuso horário. Os métodos `cancelar()` e `registrarDevolucao()` são implementados em `operacoes.py`, conforme ADR-004 e ADR-005."),
  ...figura("diagramas/02_classes.png", "Diagrama de classes"),

  H2("3.8 Diagrama de Sequência"),
  P("A devolução (UC05) é o fluxo com mais regras: lê a locação com lock, valida RN16 e RN19, apura os valores com as cinco fórmulas, finaliza a locação e decide o destino do veículo (RN18)."),
  ...figura("diagramas/04_sequencia_devolucao.png", "Sequência — registrar devolução e apurar valores (UC05)"),
  P("A reserva (UC03) concentra a regra RN06: o veículo é bloqueado, as regras de período e de cliente são verificadas e só então a sobreposição de intervalos é testada."),
  ...figura("diagramas/08_sequencia_reserva.png", "Sequência — consultar disponibilidade e reservar (UC03)"),

  H2("3.9 Ambiente de Desenvolvimento"),
  ...tabela("Ambiente de desenvolvimento", ["Item", "Ferramenta / versão"], [
    ["Linguagem", "Python 3.12 ou superior (testado em 3.13)"],
    ["Framework", "Django 5.2 LTS (5.2.18), suporte até abril de 2028"],
    ["Banco de dados", "SQLite 3 (embutido no Python)"],
    ["Interface", "Django Templates + Bootstrap 5.3.3 + Bootstrap Icons 1.11.3 (CDN jsDelivr)"],
    ["Testes", "django.test (SimpleTestCase e TestCase) — `python manage.py test`"],
    ["Ambiente virtual", "venv + pip + requirements.txt"],
    ["Versionamento", "Git + GitHub (GitHub Flow, Conventional Commits)"],
    ["Diagramas", "Mermaid (arquivos .mmd versionados em docs/diagramas)"],
    ["Protótipos", "Wireframes HTML (baixa fidelidade) e capturas das telas reais (alta fidelidade)"],
    ["Editor sugerido", "Visual Studio Code com extensões Python e Django"],
    ["Sistema operacional", "Windows, Linux ou macOS"],
  ], [1.4, 4]),
  P("Configurações relevantes em `config/settings.py`: `LANGUAGE_CODE = \"pt-br\"`, `TIME_ZONE = \"America/Sao_Paulo\"`, `USE_TZ = True`, `LOGIN_URL = \"login\"`. Variáveis de ambiente opcionais: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG` e `DJANGO_ALLOWED_HOSTS`."),

  H2("3.10 Sistemas e Componentes Externos Utilizados"),
  ...tabela("Componentes externos", ["Componente", "Uso no sistema", "Licença"], [
    ["Django 5.2 LTS", "Framework web: ORM, migrations, admin, autenticação, formulários e testes", "BSD-3-Clause"],
    ["asgiref, sqlparse", "Dependências diretas do Django", "BSD"],
    ["SQLite", "Banco de dados relacional embutido", "Domínio público"],
    ["Bootstrap 5.3.3 (CDN)", "Layout responsivo, componentes visuais e menu mobile", "MIT"],
    ["Bootstrap Icons 1.11.3 (CDN)", "Ícones da interface", "MIT"],
    ["jsDelivr", "CDN que serve o Bootstrap ao navegador", "—"],
    ["Mermaid", "Geração dos diagramas da documentação", "MIT"],
    ["GitHub", "Hospedagem do repositório e histórico de commits", "—"],
  ], [1.6, 3.6, 1.2]),
  P("O sistema não integra com serviços de pagamento, e-mail ou APIs de terceiros (ver escopo, seção 1.2.4)."),
];

// 4 ------------------------------------------------------------------------- navegador
const navegador = [
  H1("4 REQUISITOS DO NAVEGADOR / SMARTPHONE"),
  P("Por se tratar de um sistema **web**, não há instalação no computador ou celular do usuário final: basta um navegador com acesso ao endereço do servidor. Conforme o modelo do documento, este tópico substitui “Instalação e Configuração”. As instruções para executar o servidor em ambiente de desenvolvimento estão no Apêndice D e no arquivo README.md do repositório."),
  ...tabela("Navegadores suportados", ["Plataforma", "Navegador", "Versão mínima"], [
    ["Computador (Windows, macOS, Linux)", "Google Chrome / Microsoft Edge", "Últimas 2 versões (Chromium 120+)"],
    ["Computador", "Mozilla Firefox", "115 ESR ou superior"],
    ["Computador (macOS)", "Safari", "16 ou superior"],
    ["Smartphone / tablet Android", "Chrome para Android", "Últimas 2 versões"],
    ["Smartphone / tablet iOS / iPadOS", "Safari para iOS", "16 ou superior"],
  ], [2.2, 2.2, 2]),
  H3("4.1 Requisitos gerais"),
  item("JavaScript e cookies habilitados (necessários para a sessão de login, a proteção CSRF e o menu responsivo)."),
  item("Acesso à internet para carregar o Bootstrap e os ícones pela CDN jsDelivr; sem ela o sistema funciona, mas sem estilos."),
  item("Resolução mínima recomendada de 1280 × 720 no computador; em smartphones, a partir de 360 px de largura, com menu recolhível e tabelas com rolagem horizontal."),
  item("Suporte a campos de data e hora (`input type=\"datetime-local\"`), presente em todos os navegadores listados."),
  item("Conexão de rede com o servidor da aplicação (rede local da loja ou internet)."),
  H3("4.2 Acesso"),
  P("Abrir o endereço do servidor (em desenvolvimento, http://127.0.0.1:8000), entrar com o login e a senha do funcionário e utilizar o menu superior. O gerente acessa também o painel administrativo em /admin."),
];

// 5 ------------------------------------------------------------------------- desenvolvimento
const desenvolvimento = [
  H1("5 DESENVOLVIMENTO"),
  H2("5.1 Workflow de Branches"),
  P("O projeto adota o **GitHub Flow** com uma branch de integração:"),
  ...tabela("Branches do repositório", ["Branch", "Finalidade", "Regra"], [
    ["main", "Versão entregue e estável", "Recebe apenas merges de develop via Pull Request, com testes passando."],
    ["develop", "Integração do dia a dia", "Recebe as features concluídas via Pull Request."],
    ["feature/<caso-de-uso>", "Uma branch por caso de uso (ex.: feature/uc03-reserva, feature/uc05-devolucao)", "Criada a partir de develop; apagada após o merge."],
    ["fix/<descricao>", "Correções pontuais", "Mesmo fluxo das features."],
  ], [1.6, 2.6, 3]),
  P("Fluxo: criar a branch a partir de `develop` → commits pequenos e frequentes → `python manage.py test` verde → Pull Request com descrição e revisão → merge em `develop` → ao fechar a entrega, Pull Request de `develop` para `main` e tag de versão (v1.0)."),
  ...codigo([
    "git checkout develop && git pull",
    "git checkout -b feature/uc05-devolucao",
    "# ... implementar e testar ...",
    "python manage.py test",
    "git add . && git commit -m \"feat: registra devolução e apura valores (UC05)\"",
    "git push -u origin feature/uc05-devolucao   # abrir Pull Request para develop",
  ]),
  H2("5.2 Convenções de Códigos"),
  H3("5.2.1 Código Python"),
  item("Estilo **PEP 8**, linhas de até 120 caracteres, imports ordenados (biblioteca padrão, terceiros, projeto)."),
  item("Nomes do domínio em **português**, sem acentos nos identificadores (`registrar_devolucao`, `valor_diaria_aplicado`); classes em PascalCase, funções e variáveis em snake_case, constantes em MAIÚSCULAS (`TOLERANCIA_ATRASO_MIN`)."),
  item("Regras de negócio sempre em `rules.py` e fórmulas em `services.py`, como funções puras com docstring citando a regra ou fórmula (ex.: `\"\"\"RN16: km de retorno maior ou igual ao de saída.\"\"\"`)."),
  item("Violação de regra lança `RegraNegocioError(codigo, mensagem)`; a view mostra a mensagem ao usuário."),
  item("Dinheiro sempre `Decimal` com `quantize(Decimal(\"0.01\"), ROUND_HALF_UP)`; datas sempre com fuso (`django.utils.timezone.now()`)."),
  item("Toda ForeignKey declara `related_name` e `on_delete=PROTECT` para não apagar histórico."),
  H3("5.2.2 Templates e interface"),
  item("Templates em `locacao/templates/locacao/`, herdando de `base.html`; fragmentos reutilizáveis começam com `_` (`_tabela_locacoes.html`)."),
  item("Classes do Bootstrap 5, sem CSS próprio além de ajustes mínimos no `base.html`."),
  H3("5.2.3 Mensagens de commit"),
  P("Padrão **Conventional Commits**, em português, no imperativo:"),
  ...tabela("Prefixos de commit", ["Prefixo", "Uso", "Exemplo do projeto"], [
    ["feat:", "Nova funcionalidade", "feat: reescreve o sistema em Django com reserva, retirada e devolução"],
    ["test:", "Testes", "test: cobre fórmulas, regras RN01–RN19 e o ciclo completo pela interface"],
    ["docs:", "Documentação, diagramas e protótipos", "docs: adiciona diagramas, protótipos e a Documentação Final"],
    ["fix:", "Correção de defeito", "fix: impede devolução com km menor que o de saída"],
    ["chore:", "Configuração e manutenção", "chore: estrutura inicial do projeto"],
  ], [1, 2, 4.2]),
];

// 6 ------------------------------------------------------------------------- testes
const testes = [
  H1("6 ESTRATÉGIA DE TESTES"),
  H2("6.1 Pirâmide de Testes"),
  P("A estratégia segue a pirâmide de testes: muitos testes rápidos e isolados na base, sobre as fórmulas e regras puras, e menos testes, mais abrangentes, no topo, exercitando banco de dados e interface. A separação entre `services.py`/`rules.py` e o restante do código (ADR-005) é o que permite uma base larga e barata."),
  ...tabela("Pirâmide de testes do projeto", ["Nível", "Arquivo", "Qtd.", "O que cobre", "Tipo de teste"], [
    ["Topo — sistema (navegador real)", "roteiro E2E com Playwright (Chromium)", "25 passos", "Login, cadastros, busca, reserva, retirada, devolução com avaria, multa de atraso, tela de celular, ausência de erros de JavaScript e HTTP 500. Ver seção 6.3.", "Teste de sistema / aceitação"],
    ["Topo — interface (servidor)", "test_views.py · Interface, TelasDeOperacao, Cadastros", "22", "Login obrigatório em todas as rotas, todas as telas e filtros, caminhos de erro de cada formulário, admin com as mesmas validações, ciclo completo reservar → retirar → devolver com atraso (R$ 690,00) e regressões dos defeitos corrigidos.", "django.test.TestCase + Client"],
    ["Meio — integração com banco", "test_views.py · Disponibilidade, Reserva, RetiradaDevolucao, Seed", "23", "Operações reais no banco: RN01–RN06, RN08, RN11–RN19, snapshot de preço, locação de balcão, ATRASADA e EXPIRADA por tempo e o comando seed.", "django.test.TestCase"],
    ["Base — unidade (regras)", "test_rules.py", "24", "Sobreposição (8 cenários), idade, CNH, cliente inativo/atrasado, período, cancelamento, expiração, retirada e km.", "SimpleTestCase (sem banco)"],
    ["Base — unidade (fórmulas)", "test_services.py", "14", "As 5 fórmulas, frações de 24 h, tolerância exata de 60 min, HALF_UP, combustível sem crédito e o exemplo numérico completo.", "SimpleTestCase (sem banco)"],
  ], [1.6, 1.8, 0.6, 3.6, 1.6]),
  P("**Total: 83 testes automatizados, 38 deles na base da pirâmide, e 99% de cobertura de código** (medida com coverage.py). Todos passam em cerca de 13 segundos, inclusive executados em ordem aleatória (`--shuffle`), o que mostra que um teste não depende do outro."),
  P("Além dos testes automatizados, foram feitos: **testes exploratórios** com entradas inválidas em todas as telas (datas no passado, campos vazios, textos em campos numéricos, identificadores inexistentes, CPF e placa com pontuação); **teste de regressão**, rodando os testes novos contra o código antigo para confirmar que cada um detecta o defeito que protege; e **verificação de segurança** (`manage.py check --deploy`, login obrigatório em todas as rotas, proteção CSRF e escape de HTML)."),
  H3("6.1.1 O que ficou de fora"),
  item("**Testes de carga e concorrência real**: a proteção por `select_for_update` só tem efeito pleno em PostgreSQL; com SQLite as escritas já são serializadas."),
  item("**Testes de usabilidade com usuários finais** e testes de acessibilidade automatizados."),
  item("**Configurações de HTTPS** apontadas por `check --deploy` (HSTS, cookies seguros, redirecionamento SSL): não se aplicam à execução local em http://127.0.0.1 e devem ser ativadas apenas numa publicação na internet."),
  H2("6.2 Execução"),
  P("Com o ambiente virtual ativado, na raiz do projeto:"),
  ...codigo([
    "python manage.py test                          # todos os testes",
    "python manage.py test locacao.tests.test_services   # só as fórmulas",
    "python manage.py test locacao.tests.test_rules      # só as regras",
    "python manage.py test -v 2                     # lista cada teste executado",
    "python manage.py test --shuffle                # ordem aleatória",
    "pip install coverage                           # opcional: medir a cobertura",
    "coverage run --source=locacao manage.py test && coverage report",
  ]),
  P("Saída esperada:"),
  ...codigo([
    "Found 83 test(s).",
    "Creating test database for alias 'default'...",
    "System check identified no issues (0 silenced).",
    "...................................................................................",
    "----------------------------------------------------------------------",
    "Ran 83 tests in 13.2s",
    "",
    "OK",
  ]),
  P("O banco de testes é criado e destruído automaticamente; os dados de desenvolvimento (`db.sqlite3`) não são afetados. Os testes devem ser executados antes de cada commit e de cada Pull Request."),
  H2("6.3 Teste de sistema (aceitação no navegador)"),
  P("Roteiro executado no navegador Chromium, com o servidor rodando (`runserver`) e os dados do `seed`, cobrindo os cinco casos de uso de ponta a ponta. Pode ser repetido manualmente pelo avaliador seguindo a mesma sequência."),
  ...tabela("Roteiro de teste de sistema e resultado", ["Passo", "Ação", "Resultado esperado", "Resultado"], [
    ["1", "Abrir o sistema sem login; entrar com senha errada; entrar com atendente/locadora123", "Redireciona ao login; mostra “Usuário ou senha inválidos”; abre o painel com 5 indicadores", "OK"],
    ["2", "UC02: cadastrar cliente com CPF 935.411.347-80 (com pontuação)", "“Cliente salvo com sucesso”", "OK"],
    ["3", "UC01: cadastrar veículo com placa “tst-9e99”", "Veículo salvo com placa TST9E99", "OK"],
    ["4", "UC03: buscar Econômico por 3 dias", "Veículo novo listado, valor estimado R$ 360,00", "OK"],
    ["5", "UC03: reservar para o cliente novo", "Reserva confirmada com código RES-AAAA-XXXXXX", "OK"],
    ["6", "RN06: repetir a mesma busca", "Veículo reservado não aparece mais", "OK"],
    ["7", "UC04: registrar retirada com km menor que o do veículo; depois com o km correto", "Erro RN14; depois “Retirada registrada”, locação Em andamento", "OK"],
    ["8", "UC05: devolver com meio tanque e calcular extrato", "Extrato com diárias, multa e combustível (R$ 150,00)", "OK"],
    ["9", "UC05: marcar avaria sem descrição; descrever e confirmar", "Erro “Descreva a avaria”; depois devolução registrada, caução retida", "OK"],
    ["10", "RN18: consultar o veículo", "Status Em manutenção", "OK"],
    ["11", "RN17: devolver a locação atrasada do seed", "Extrato com multa “× 1,5”", "OK"],
    ["12", "Abrir em tela de celular (375 px) e usar o menu", "Sem rolagem horizontal; menu recolhível abre", "OK"],
    ["13", "Durante todo o roteiro", "Nenhum erro de JavaScript nem HTTP 500", "OK"],
  ], [0.6, 3, 3, 0.8]),
];

// 7 ------------------------------------------------------------------------- referências
const referencias = [
  H1("7 REFERÊNCIAS E RECURSOS"),
  P("ASSOCIAÇÃO BRASILEIRA DE NORMAS TÉCNICAS. **NBR 14724**: informação e documentação — trabalhos acadêmicos — apresentação. Rio de Janeiro: ABNT, 2011."),
  P("BOOTSTRAP. **Bootstrap 5.3 documentation**. Disponível em: https://getbootstrap.com/docs/5.3/. Acesso em: 11 out. 2026."),
  P("CONVENTIONAL COMMITS. **Conventional Commits 1.0.0**. Disponível em: https://www.conventionalcommits.org/pt-br/v1.0.0/. Acesso em: 11 out. 2026."),
  P("DJANGO SOFTWARE FOUNDATION. **Django 5.2 documentation**. Disponível em: https://docs.djangoproject.com/pt-br/5.2/. Acesso em: 11 out. 2026."),
  P("EVANS, Eric. **Domain-Driven Design**: atacando as complexidades no coração do software. 3. ed. Rio de Janeiro: Alta Books, 2016."),
  P("FOWLER, Martin. **UML essencial**: um breve guia para a linguagem-padrão de modelagem de objetos. 3. ed. Porto Alegre: Bookman, 2005."),
  P("GITHUB. **GitHub flow**. Disponível em: https://docs.github.com/pt/get-started/using-github/github-flow. Acesso em: 11 out. 2026."),
  P("MERMAID. **Mermaid documentation**. Disponível em: https://mermaid.js.org/. Acesso em: 11 out. 2026."),
  P("NYGARD, Michael. **Documenting architecture decisions**. 2011. Disponível em: https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions. Acesso em: 11 out. 2026."),
  P("PYTHON SOFTWARE FOUNDATION. **PEP 8 – Style Guide for Python Code**. Disponível em: https://peps.python.org/pep-0008/. Acesso em: 11 out. 2026."),
  P("PYTHON SOFTWARE FOUNDATION. **decimal — Decimal fixed point and floating point arithmetic**. Disponível em: https://docs.python.org/3/library/decimal.html. Acesso em: 11 out. 2026."),
  P("SOMMERVILLE, Ian. **Engenharia de software**. 10. ed. São Paulo: Pearson, 2018."),
  P("VOCKE, Ham. **The practical test pyramid**. 2018. Disponível em: https://martinfowler.com/articles/practical-test-pyramid.html. Acesso em: 11 out. 2026."),
  H3("Recursos do projeto"),
  item("Repositório: https://github.com/bruno011203/projeto-da-loca-o-de-carros"),
  item("Documentos de base: “Locadora de Veículos — Modelo de Domínio e Regras de Negócio” e “Stack e passo a passo” (10/10/2026)."),
  item("Fontes dos diagramas: `docs/diagramas/*.mmd`; protótipos: `docs/prototipos/`; gerador deste documento: `docs/fonte/gerar_documentacao.js`."),
];

// 8 ------------------------------------------------------------------------- apêndices
const apendices = [
  H1("8 APÊNDICES"),
  H2("Apêndice A — Trabalho futuro"),
  ...tabela("Itens fora do escopo e proposta de evolução", ["Item", "Proposta"], [
    ["Pagamento", "Integração com gateway (cartão/Pix) para caução e cobrança final, com estorno automático da caução."],
    ["Permissões por perfil", "Restringir cadastro de categorias e preços ao GERENTE com grupos/permissões do Django; o perfil já está modelado em Funcionario."],
    ["Avarias com fotos", "Entidade de vistoria com upload de imagens na retirada e na devolução; desconto da avaria na caução."],
    ["Relatórios gerenciais", "Faturamento por período e categoria, taxa de ocupação da frota, ranking de clientes."],
    ["Multi-filial", "Entidade Filial; retirada e devolução em lojas diferentes com taxa de retorno."],
    ["Notificações", "E-mail/WhatsApp de confirmação de reserva, lembrete de devolução e aviso de atraso."],
    ["API REST", "Django REST Framework para aplicativo móvel e parceiros."],
    ["Agendador", "Substituir a avaliação preguiçosa (ADR-006) por tarefa agendada, caso surjam notificações por tempo."],
  ], [1.4, 4.4]),
  H2("Apêndice B — Modelo físico do banco de dados"),
  P("Tabelas geradas pelas migrations do Django (prefixo `locacao_`). A tabela `auth_user` pertence ao módulo de autenticação do Django."),
  ...figura("diagramas/07_banco_de_dados.png", "Diagrama entidade-relacionamento (modelo físico)", { largura: 470 }),
  H2("Apêndice C — Estrutura do projeto"),
  ...codigo([
    "projeto-da-loca-o-de-carros/",
    "├── manage.py",
    "├── requirements.txt          Django 5.2.18, asgiref, sqlparse",
    "├── README.md",
    "├── config/                   settings.py · urls.py · wsgi.py · asgi.py",
    "├── locacao/",
    "│   ├── enums.py              6 enumerações do domínio",
    "│   ├── models.py             7 entidades",
    "│   ├── validators.py         validação de CPF",
    "│   ├── services.py           5 fórmulas de cálculo (funções puras)",
    "│   ├── rules.py              RN01–RN19 (funções puras)",
    "│   ├── operacoes.py          UC03–UC05 (transações)",
    "│   ├── forms.py · views.py · urls.py · admin.py",
    "│   ├── templatetags/         filtros moeda, milhar e selo de status",
    "│   ├── management/commands/seed.py",
    "│   ├── migrations/",
    "│   ├── templates/            locacao/*.html · registration/login.html",
    "│   └── tests/                test_services.py · test_rules.py · test_views.py",
    "└── docs/",
    "    ├── diagramas/            *.mmd e *.png",
    "    ├── prototipos/           baixa_*.png e alta_*.png",
    "    ├── fonte/                gerar_documentacao.js",
    "    └── Documentacao_Final.docx",
  ]),
  H2("Apêndice D — Execução em ambiente de desenvolvimento"),
  P("Pré-requisitos: Python 3.12 ou superior e Git."),
  ...codigo([
    "git clone https://github.com/bruno011203/projeto-da-loca-o-de-carros.git",
    "cd projeto-da-loca-o-de-carros",
    "python -m venv .venv",
    "source .venv/bin/activate           # Windows: .venv\\Scripts\\activate",
    "pip install -r requirements.txt",
    "python manage.py migrate",
    "python manage.py seed               # dados de exemplo (--reset para recriar)",
    "python manage.py runserver          # http://127.0.0.1:8000",
  ]),
  ...tabela("Usuários criados pelo comando seed", ["Login", "Senha", "Perfil", "Acesso"], [
    ["gerente", "locadora123", "GERENTE", "Sistema e painel administrativo (/admin)"],
    ["atendente", "locadora123", "ATENDENTE", "Sistema"],
  ], [1.2, 1.4, 1.4, 3]),
  P("Os dados de exemplo incluem 4 categorias, 10 veículos (1 em manutenção), 5 clientes — entre eles um com 20 anos (para demonstrar RN01) e um com CNH categoria A (RN02) —, uma locação finalizada que reproduz o exemplo numérico (R$ 690,00), uma locação em andamento, uma atrasada e duas reservas futuras."),
  H2("Apêndice E — Matriz de rastreabilidade"),
  ...tabela("Requisito → caso de uso → regra → teste", ["Requisito", "Caso de uso", "Regras", "Testes"], [
    ["RF02, RF03", "UC01", "RN05, RN07", "test_rn05_rn07_busca_ignora_manutencao_inativo_e_reservados"],
    ["RF04, RF16", "UC02", "RN01, RN02, RN03", "test_rn01_*, test_rn02_*, test_rn03_*, test_cadastro_de_cliente_valida_cpf"],
    ["RF05, RF06", "UC03", "RN04, RN06, RN08–RN10", "SobreposicaoTests, test_rn06_reserva_sobreposta_e_recusada, test_rn08_*, test_rn09_*, test_rn10_*"],
    ["RF07, RF08", "UC03", "RN11, RN12", "test_rn11_cancelamento_*, test_rn12_*"],
    ["RF09, RF10", "UC04", "RN13, RN14, RN15", "test_rn13_*, test_rn14_*, test_rn15_*, test_locacao_de_balcao_sem_reserva"],
    ["RF11, RF12, RF13", "UC05", "RN16–RN19", "test_exemplo_do_documento_e_rn18_sem_avaria, test_rn18_avaria_*, test_rn16_*, test_rn19_*, test_atrasada_por_tempo"],
    ["RF01, RF14, RF15", "—", "—", "test_login_obrigatorio, test_paginas_carregam, test_ciclo_completo_pela_interface"],
  ], [1.4, 1, 1.6, 4]),
  H2("Apêndice F — Registro de defeitos encontrados nos testes"),
  P("Defeitos encontrados nos testes exploratórios e de sistema, todos corrigidos e protegidos por teste de regressão (o teste falha no código antigo e passa no corrigido)."),
  ...tabela("Defeitos encontrados e corrigidos", ["#", "Defeito", "Correção", "Teste de regressão"], [
    ["D1", "Erro 500 ao abrir a tela de nova reserva com identificador de veículo inválido na URL", "A tela volta para a busca de disponibilidade", "test_reserva_com_parametros_invalidos_volta_para_a_busca"],
    ["D2", "Devolver no mesmo minuto da retirada dava erro RN16, porque a retirada guardava segundos e a tela trabalha com minutos", "Retirada gravada sem segundos; comparações com precisão de minuto", "test_devolucao_logo_apos_a_retirada"],
    ["D3", "Prévia do extrato era exibida mesmo com data de devolução anterior à retirada", "A prévia valida data (RN16), km (RN16) e avaria antes de calcular", "test_devolucao_valida_data_km_e_avaria_antes_do_extrato"],
    ["D4", "Placa digitada com hífen (ABC-1D23) era recusada por ter 8 caracteres", "Campo aceita hífen e minúsculas e normaliza para ABC1D23", "test_placa_com_hifen_e_minusculas_e_normalizada"],
    ["D5", "Cliente podia ser cadastrado com data de nascimento no futuro", "Validação de data de nascimento no passado", "test_cliente_com_cpf_formatado_e_nascimento_futuro"],
    ["D6", "Busca aceitava período no passado ou maior que 30 dias, e o erro só aparecia ao confirmar a reserva; no admin, CPF com pontuação e placa com hífen eram recusados e o status LOCADO podia ser definido à mão", "Busca aplica RN08, RN09 e RN10; o admin usa os mesmos formulários das telas", "test_busca_aplica_rn08_rn09_rn10, test_admin_usa_as_mesmas_validacoes"],
  ], [0.5, 3.2, 2.4, 2.4]),
];

// --------------------------------------------------------------------------- documento

const doc = new Document({
  creator: AUTOR,
  title: TITULO,
  description: "Documentação final do projeto",
  styles: {
    default: { document: { run: { font: FONTE, size: 24 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, font: FONTE, color: COR_TITULO },
        paragraph: { spacing: { before: 240, after: 240 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: FONTE, color: COR_TITULO },
        paragraph: { spacing: { before: 300, after: 160 }, outlineLevel: 1, keepNext: true } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: FONTE, color: "2F5496" },
        paragraph: { spacing: { before: 220, after: 120 }, outlineLevel: 2, keepNext: true } },
    ],
  },
  numbering: {
    config: [
      { reference: "marcadores", levels: [
        { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
        { level: 1, format: LevelFormat.BULLET, text: "◦", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 1440, hanging: 360 } } } },
      ] },
      { reference: "numeros", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.",
        alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "camadas", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.",
        alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ],
  },
  features: { updateFields: true },
  sections: [
    { properties: { page: { size: PAGINA, margin: MARGEM } }, children: capa },
    {
      properties: { page: { size: PAGINA, margin: MARGEM } },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
        children: [new TextRun({ children: [PageNumber.CURRENT], size: 20 })] })] }) },
      children: [...historico, ...visaoGeral, ...arquitetura, ...especificacao, ...navegador,
        ...desenvolvimento, ...testes, ...referencias, ...apendices],
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(SAIDA, buf);
  console.log(`Gerado ${SAIDA} (${numeroFigura} figuras, ${numeroTabela} tabelas)`);
});
