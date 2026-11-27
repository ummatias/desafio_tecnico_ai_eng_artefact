# Achados de qualidade dos dados

Revisado à mão a partir de `data/*.csv` e do Manual de Políticas v2.1, em 2026-11-27. Só entra o
achado que tem consequência de design. **Confirmado** = verificado nos dados; **Não verificável** =
os dados não permitem concluir.

| # | Achado | Rótulo | Consequência de design |
|---|---|---|---|
| A01 | Pedido 8 `shipped` com previsão em 2026-02-28; pedidos 9–16 em `pending`/`confirmed` desde fev–mar/2026, sem previsão | Confirmado | `get_order` devolve `delivery_state` (`on_time`, `late`, `stalled`) e `days_late`; o agente reconhece o atraso, mostra o rastreio quando existe e escala com prioridade. Nunca só "está pendente" |
| A02 | Os 7 pedidos de Campo Grande com previsão (1, 2, 3, 4, 5, 7, 8) têm de 10 a 15 dias corridos e rastreio no formato dos Correios; o §5.1 diz motoboy em 1 a 3 dias úteis | Confirmado | `estimated_delivery` nunca decide um direito: só encaminha o caso |
| A03 | Pedidos PIX 1, 5, 10, 13 e 17 gravados a preço de tabela, sem os 5% do §3 | Confirmado | Significado de `total_brl` desconhecido: "valor do pedido", nunca "você pagou" |
| A04 | Parcela abaixo do mínimo do §3.1 nos pedidos 9 (6x de R$ 58,31), 16 (6x de R$ 71,65) e 18 (12x de R$ 38,32); a política v2.1 (junho/2025) é anterior a todos os pedidos | Confirmado | Regras só da política, nunca do histórico; o agente nunca diz ao cliente que o pedido dele violou uma regra |
| A05 | Produto 130 (`coming_soon`) nos pedidos 3 (entregue) e 14 | Confirmado | Só relatado; nunca oferecido como disponível |
| A06 | Produto 96 ativo com estoque zero; 113 e 136 descontinuados (136 ainda com 13 unidades) | Confirmado | Indisponível + alternativas (§7.3); descontinuado não é vendido nem com estoque |
| A07 | Produtos 135–144: nome, descrição e specs se contradizem (135 "Music Man" descrito como Fender Jazz Bass; 142 "Korg" descrito como Roland de 88 teclas, specs 61). Indícios de lote gerado à parte: JSON de specs com outra formatação (10 de 10) e preço fora do padrão da loja (9 de 10; exceção: 139, R$ 4.439,00) | Confirmado | `inconsistent_listing`, a partir de `knowledge/catalog_review.yaml`: nem o nome nem a descrição geram resposta definitiva, positiva ou negativa |
| A08 | Só as promoções 12, 14, 19 e 24 estão ativas; nenhuma de Black Friday; linhas repetidas por produto (93, 96, 99); sem datas | Confirmado | O sistema é a fonte da verdade: só a promoção ativa vale |
| A09 | Clientes 11 e 43 compartilham o mesmo e-mail: provável duplicidade de cadastro, a confirmar pela loja. Categorias 6, 7 e 8 sem produtos | Confirmado | Identidade pelo telefone; o agente não junta os dois cadastros. Categoria vazia tem resposta própria |
| A10 | Pedidos 3 e 20 diferem da soma dos itens a preço atual; pedidos 2 e 11 contêm produto com promoção ativa hoje, mas foram gravados a preço cheio | Não verificável | Sem preço unitário histórico nem datas de promoção: só relatado, sem conclusão para o cliente |

**Notas do A02**
- O prazo conta da data do pedido. O pedido 4 é boleto: contando da compensação (§3, até 3 dias
  úteis), o limite vira 6 dias úteis, contra 8 até a previsão. Excede mesmo assim.
- Feriados conferidos em cada janela: 20/11 (pedido 3) é o próprio dia do pedido e não conta;
  15/11 (pedido 2) caiu num sábado. Os pedidos 7 e 8 incluem o Carnaval (16 e 17/02/2026, ponto
  facultativo); mesmo descontando esses dois dias, ficam com 8 dias úteis.
