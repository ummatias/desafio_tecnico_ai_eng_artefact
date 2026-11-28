# Empório da Música — Agente de Atendimento

Agente de atendimento por mensagens de texto para a Empório da Música, loja fictícia de instrumentos musicais em Campo Grande/MS. Responde sobre produtos, preços, pedidos, trocas, horários e formas de pagamento usando os CSVs de `data/` e o manual de políticas (`knowledge/policies.md`, transcrito do PDF).

## Como funciona

O modelo escolhe quais ferramentas chamar e escreve a resposta. Preços, totais, parcelas, frete, prazos e elegibilidade de troca são calculados por código Python testado e chegam ao modelo prontos, já formatados em pt-BR.

```
mensagem -> loop de tool calling (até 5 iterações) -> tools -> domínio -> SQLite (semeado dos CSVs)
                 |
                 +-> resposta -> trace JSONL com dados pessoais mascarados (var/traces/)
```

Se o loop não chega a uma resposta, o agente faz uma última chamada sem ferramentas. Se ainda assim falhar, o código abre um chamado e devolve o protocolo ao cliente.

| Tool | O que faz |
|---|---|
| `search_products` | Busca por nome, categoria, faixa de preço e tipo de corda |
| `get_product` | Preço, promoção, PIX e parcelas válidas de um produto |
| `quote_cart` | Total de um carrinho com frete, PIX e parcelas |
| `get_order` | Pedido do cliente identificado, com situação da entrega (`on_time`, `late`, `stalled`) |
| `check_exchange` | Arrependimento, troca, defeito e garantia |
| `get_policy` | Uma seção do manual |
| `escalate_to_human` | Abre chamado com protocolo e prazo de retorno |

---

## Requisitos

- Python 3.12 + [uv](https://docs.astral.sh/uv/), ou Docker + Docker Compose
- Chave do [OpenRouter](https://openrouter.ai/) para conversar com o agente. Os testes não precisam dela.

---

## Setup

### Local

```bash
cp .env.example .env        # preencher LLM_API_KEY
uv sync
uv run python -m emporio.db.seed
make chat PHONE="(67) 99654-7821"
```

O seed cria `var/emporio.db` a partir de `data/` e só roda se o banco estiver vazio. Depois de mudar o schema, use `--force`.

### Docker

```bash
cp .env.example .env
docker compose build cli
HOST_UID=$(id -u) HOST_GID=$(id -g) docker compose run --rm cli chat --phone "(67) 99654-7821"
```

A imagem já leva os CSVs, o manual e as fixtures. Só `./var` (banco, traces e relatórios) é montado. `HOST_UID`/`HOST_GID` fazem os arquivos de `./var` ficarem com o seu usuário. Como a CLI é interativa, use `docker compose run`, não `up`.

---

## Configuração

Tudo fica no `.env`:

| Variável | Padrão | Descrição |
|---|---|---|
| `LLM_API_KEY` | — | Chave do OpenRouter. Sem ela a CLI sai com código 2 |
| `LLM_MODEL` | `openai/gpt-oss-120b` | Qualquer modelo do OpenRouter com tool calling |
| `LLM_PROVIDERS` | `baseten` | Provider fixo, sem fallback. Vazio usa o roteamento padrão |
| `LLM_TEMPERATURE` | `0.2` | |
| `LLM_DATA_COLLECTION` | `deny` | Só providers que não guardam as conversas |
| `REFERENCE_DATE` | vazio | Data de "hoje" (`2026-11-26` ou `2026-11-26T10:00`). Vazio usa o relógio |
| `TRACKING_SOURCE` | `none` | `fixture` usa o rastreio sintético de `fixtures/delivery_events.csv` |
| `EVAL_JUDGE_MODEL` | vazio | Modelo que avalia o tom nos evals |

---

## Uso

### Conversa

```bash
make chat PHONE="(67) 99654-7821" DEBUG=1
REFERENCE_DATE=2026-11-26 uv run emporio chat --phone "(67) 99654-7821" --debug
make docker-chat PHONE="(67) 99654-7821" REFERENCE_DATE=2026-11-26
```

O telefone faz o papel do número que o WhatsApp já verificou. Sem telefone, o cliente não é identificado e não consegue consultar pedidos. `--debug` mostra as tools chamadas, os tokens e o custo de cada turno. `/limpar` zera o histórico e `/sair` encerra.

Clientes úteis para testar:

| Telefone | Cliente | Situação |
|---|---|---|
| `(67) 99654-7821` | Ana | Pedido 8 enviado e atrasado |
| `(67) 98765-4321` | Rafael | Pedido 5, com rastreio na fixture (entregue em 12/01/2026) |
| `(67) 99234-5678` | Juliana | Pedido 9 parado desde fevereiro |
| `(67) 98654-3210` | Gabriel | Mora em Dourados (frete sob cotação) |

### Exemplos de conversa

Gerados pelo agente com `uv run python scripts/gen_examples.py`, sem edição. Cada arquivo traz a data de referência, o modelo, o provider, as tools de cada turno e o custo.

| Arquivo | Cenário |
|---|---|
| [01-violoes-ate-1000](examples/01-violoes-ate-1000.md) | Violões até R$ 1.000 e parcelamento |
| [02-carrinho-gd20](examples/02-carrinho-gd20.md) | Preço do Takamine GD20 e carrinho com frete e PIX |
| [03-defeito-garantia-legal](examples/03-defeito-garantia-legal.md) | Defeito 40 dias após a compra, coberto pela garantia legal |
| [04-arrependimento](examples/04-arrependimento.md) | Arrependimento fora do prazo e "recebi ontem" |
| [05-pedido-endereco-escopo](examples/05-pedido-endereco-escopo.md) | Horário, pedido atrasado, acessório e pedido de outro cliente |

---

## Testes

```bash
make test                   # pytest, sem chave de API
make lint                   # ruff check, ruff format --check, mypy
uv run pytest -m live -s    # uma chamada real ao OpenRouter
```

Os testes do domínio usam valores calculados à mão a partir do manual, e cada premissa de `docs/assumptions.md` aponta para o teste que a cobre. O CI (`.github/workflows/ci.yml`) roda lint e testes a cada push.

---

## Evals

```bash
make eval                           # 28 casos x 3 execuções (~5 min, ~US$ 0,08)
make eval ONLY=produto-gd20 RUNS=1
make docker-eval ONLY=produto-gd20 RUNS=1
uv run emporio eval compare var/evals/A/results.json var/evals/B/results.json
```

Os casos ficam em `evals/cases/`, um YAML por caso, com os fatos esperados escritos à mão, as tools esperadas, o resultado da política de trocas e se o caso deve ir para um atendente. Cada caso roda 3 vezes, sempre com banco novo. O relatório conta casos, não execuções: um caso que passa nas 3 é `stable_pass`, um que passa em algumas é `flaky`, um que não passa em nenhuma é `stable_fail`. A saída vai para `var/evals/<data>-<modelo>/`.

| Rodada | stable_pass / flaky / stable_fail | Execuções que passaram |
|---|---|---|
| [Linha de base](evals/results/baseline.md), prompt v1 | 18 / 6 / 4 | 61/84 |
| [Depois dos ajustes](evals/results/after-prompt-fixes.md), prompt v2 | 22 / 6 / 0 | 77/84 |

Na rodada final, 14% dos casos foram escalados (meta de até 25%), e a latência mediana foi de 2,8 s por turno.

Esses números têm limites. Os mesmos casos foram usados para ajustar o prompt e para medir o resultado, então são otimistas; não houve tempo para um conjunto separado. Com 28 casos, diferença de um ou dois casos entre versões é ruído. E o check é por presença de texto: uma regra explicada errado sem nenhum número errado passa.

---

## Análise dos dados

Antes de escrever código, auditei os CSVs e o manual. O relatório completo está em [docs/data_quality_report.md](docs/data_quality_report.md).

| Arquivo | Linhas | Conteúdo |
|---|---|---|
| `products.csv` | 65 | Preço, estoque, status, categoria e specs em JSON |
| `categories.csv` | 9 | 3 categorias sem nenhum produto (sopros e cordas orquestrais) |
| `orders.csv` / `order_items.csv` | 20 / 22 | Pedidos de out/2025 a mar/2026 |
| `customers.csv` | 50 | Nome, telefone, e-mail e cidade |
| `promotions.csv` | 25 | 4 ativas, nenhuma com data |

**Pedidos.** O pedido 8 está `shipped` com previsão para 28/02/2026, e os pedidos 9 a 16 estão parados em `pending` ou `confirmed` desde fevereiro e março. Os pedidos de Campo Grande levaram de 10 a 15 dias para uma entrega que o manual promete em 1 a 3 dias úteis. Por isso `get_order` calcula o atraso, e o agente pede desculpas e oferece encaminhar em vez de responder "está pendente".

**Preços e pagamentos.** Pedidos pagos no PIX foram registrados sem os 5% de desconto, e três pedidos têm parcela abaixo do mínimo do §3.1 (o pior é 12x de R$ 38,32). A política é anterior a todos esses pedidos, então as regras vêm sempre do manual e nunca do histórico. O agente fala em "valor do pedido", nunca em "você pagou", e não aponta ao cliente regras que o próprio pedido dele quebrou.

**Catálogo.** Nos produtos 135 a 144, nome, descrição e specs não batem. O 135 se chama "Music Man", mas a descrição é de um Fender Jazz Bass. O 142 é um "Korg" descrito como Roland de 88 teclas, com specs de 61. O formato do JSON e os preços também fogem do padrão, o que indica um lote importado separado. Esses itens estão listados em `knowledge/catalog_review.yaml`, e o agente diz que o cadastro está em revisão, sem confirmar nem negar o produto. O produto 96 está ativo com estoque zero, e o 136 está descontinuado mas ainda tem 13 unidades. Indisponível é oferecido com alternativas, e descontinuado não é vendido.

**Promoções e clientes.** Só 4 promoções estão ativas, sem datas, algumas repetidas para o mesmo produto, e nenhuma é de Black Friday, embora o manual fale em descontos de 15% a 30%. O agente só usa promoção ativa no sistema. Dois clientes dividem o mesmo e-mail; o cliente é identificado sempre pelo telefone.

**Manual.** O §1.2 dá (67) 3341-4444 como telefone e WhatsApp, e o §7 dá (67) 3321-4500 como WhatsApp. O e-mail aparece com e sem acento. O manual manda sugerir lojas parceiras, mas não cita nenhuma, e não lista os feriados.

Cada lacuna virou uma premissa numerada em [docs/assumptions.md](docs/assumptions.md). Estas precisam ser confirmadas pela loja:

- **P-09:** feriados municipais (13/06, 26/08 e Corpus Christi). Carnaval tem horário normal, com aviso para confirmar.
- **P-10:** períodos de Natal (01/12 a 24/12) e Aniversário da Loja (agosto), em que o horário pode ser estendido.
- **P-12:** região metropolitana tratada como "cidade Campo Grande".
- **P-13:** WhatsApp (67) 3321-4500, telefone (67) 3341-4444 e e-mail sem acento.

---

## Implementation Decisions


**Tool calling em vez de RAG** (`src/emporio/tools/`): o manual tem cerca de 3 mil tokens em seções numeradas, e as perguntas pedem valores exatos (preço, pedido, prazo). As regras viraram código, e o manual é consultado por número de seção em `get_policy`.

**Sem text-to-SQL** (`src/emporio/repositories/orders.py`): as perguntas se repetem e cabem em 7 tools. A posse do pedido é checada dentro da consulta, então um cliente não consegue ver o pedido de outro.

**Sem MCP e sem framework de agentes** (`src/emporio/agent/loop.py`): as tools só servem a este agente, e o fluxo é linear. O loop é escrito à mão e controla o limite de iterações, o fallback e o formato das saídas das tools. As tools já são funções com schema pydantic; se outro sistema precisar delas, dá para expô-las por MCP depois.

**Valores em centavos inteiros** (`src/emporio/domain/pricing.py`, `installments.py`): descontos são truncados (P-22), e na divisão das parcelas a sobra vai para a primeira (P-05). O mínimo de parcela é checado na menor delas.

**Só o rastreio decide a data de recebimento** (`src/emporio/domain/exchange.py`, `src/emporio/tracking.py`): o arrependimento e a garantia legal contam do recebimento. A data da compra pode garantir um direito, mas nunca negá-lo (P-24). A data dita pelo cliente vai para o chamado e não muda a decisão (P-17). Sem rastreio, o caso fica `to_confirm` e vai para um atendente.

**Prazo vencido não vira chamado** (`src/emporio/agent/prompts/system_v2.md`): o cliente recebe um "não" claro, com alternativas. Só se abre chamado quando `check_exchange` pede. A taxa de escalada é medida nos evals.

**Saída das tools marcada como dado** (`src/emporio/agent/loop.py`): cada resultado volta como `{"kind": "tool_result", "untrusted_data": true, "data": ...}`, para que texto vindo do banco não seja lido como instrução. Respostas com marcadores do formato interno do modelo (`<|start|>`, `<|call|>`) são descartadas e a chamada é repetida.

**`gpt-oss-120b` via OpenRouter** (`src/emporio/llm/openrouter.py`): pesos abertos, tool calling nativo e cerca de US$ 0,001 por turno. Trocar de modelo é só mudar `LLM_MODEL`. Nos evals, o provider fica fixo, porque o mesmo modelo muda de qualidade entre providers.

**Temperatura 0.2** (`src/emporio/config.py`): a OpenAI recomenda 1.0 para o gpt-oss. Com o mesmo provider, 0.2 deixou menos casos instáveis (5 contra 7), mas a diferença está dentro do ruído.

**Telefones e e-mails mascarados no trace** (`src/emporio/observability/masking.py`): o trace guarda a conversa para depuração, sem dados pessoais. Os únicos números que ficam são os da loja, e só na forma exata.

**CLI como interface** (`src/emporio/cli.py`): mostra as tools e o custo de cada turno, o que ajuda a avaliar o agente. O histórico fica na memória da sessão.

---

## Limitações

- Nenhum código confere a resposta final. Um valor ou protocolo inventado pelo modelo não é bloqueado; os evals só medem.
- Nos exemplos: o agente não informa o endereço da loja e escala o pedido atrasado sem perguntar ao cliente (exemplo 5). Também abre um segundo chamado no turno seguinte, porque o limite de um chamado vale por turno (exemplo 3).
- Em 1 de 3 execuções, o agente afirmou "consertamos sim" sem base no manual e disse que "algumas ofertas chegam a 30%" sem promoção ativa.
- O histórico não tem limite de tamanho e se perde ao fechar a CLI.
- Com o provider fixado e sem fallback, uma rodada inteira de evals falhou enquanto o BaseTen estava fora do ar.
- O rastreio é uma fixture sintética para os pedidos 1 a 5.
- O telefone é aceito como verificado; não há integração com o WhatsApp.
- Não há valor de frete fora de Campo Grande, porque os dados não trazem CEP nem tabela.
- Não houve comparação com outro modelo, e o juiz de tom não foi usado.

## Próximos passos

1. Conferir por código, antes de enviar, que todo valor em R$ e todo protocolo da resposta vieram de uma tool, do prompt ou da mensagem do cliente.
2. Corrigir os erros vistos nos exemplos.
3. Comparar com um modelo de ponta nos mesmos casos.
4. API `/chat` com sessões persistidas por telefone, expirando em 24 h, e histórico limitado aos últimos turnos.
5. Mais casos de eval e um conjunto separado só para medir.
6. Integração real de rastreio e de cotação de frete.

---

## Uso de assistentes de código

Usei o Claude Code para estruturação da base de conhecimento, yamls, assumptions e premissas, transformando texto desestruturado em dados. 

Trabalhei em ciclos curtos. Para cada etapa, o Claude Code escrevia um plano a partir do enunciadoEu aprovava, ajustava ou recusava o plano antes e então partia para a implementação. O Claude revisava minha implementação e sugeria testes, que eu escrevia e rodava. O loop se repetia até que o plano fosse concluído.

Algumas decisões que tomei ao revisar os planos:
- antes de abrir um chamado, fazer uma última chamada ao modelo sem ferramentas;
- cortar o conjunto separado de evals e commitar a linha de base antes de qualquer ajuste de prompt;
- trocar um teste que usava um vazamento escrito à mão pelo texto real capturado num eval;
- definir a regra para escolher a temperatura e o critério de parada dos ajustes de prompt.

Regras que valeram o projeto inteiro:
- os valores esperados nos testes e evals são escritos à mão a partir do manual, nunca calculados pelo código testado;

A revisão do Copilot encontrou problemas no loop do agente, como `session_id` sem máscara no trace e chamado duplicado no mesmo turno. Os evals encontraram um protocolo inventado, a resposta do modelo vazando em formato interno e a busca falhando com o nome da categoria. Também mostraram casos de eval mal escritos, que rejeitavam respostas corretas por causa de sinônimos.
