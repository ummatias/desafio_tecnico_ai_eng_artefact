# Premissas

Leituras adotadas onde o Manual de Políticas ([`knowledge/policies.md`](../knowledge/policies.md))
é omisso, ambíguo ou contraditório, ou onde os dados não trazem a informação. 

**Onde há premissa, ela prevalece sobre a leitura literal.**

Cada premissa aponta para o teste que a fixa, a partir da implementa a regra. Até lá, o
campo diz `pendente`.

**Status:** `adotada`, ou `a confirmar pela loja`

Formato fixo de cada item, para busca com `rg "^ID: P-xx" -A4`: ID, Seção, Status, Teste,
Premissa, Motivo.

---

### P-01 · Defeito: troca na loja, garantia legal, garantia do fabricante
ID: P-01
Seção: §4.2, §8.1, §8.2
Status: adotada
Teste: pendente
Premissa: defeito em até 30 dias corridos da compra → troca pela loja (§4.2), decidida sem data de recebimento. Depois disso, e em até 90 dias do recebimento → garantia legal (§8.1): registrar e escalar, **nunca** "só com o fabricante". Depois dos 90 dias → garantia do fabricante (§8.2), com a loja podendo intermediar.
Motivo: o §4.2 manda acionar o fabricante após 30 dias, mas o §8.1 (CDC) garante 90 dias a partir do recebimento. A garantia legal não pode ser negada pelo manual.

### P-02 · Valores exatos de R$ 500,00 e R$ 2.000,00
ID: P-02
Seção: §5.1, §3.1
Status: adotada
Teste: pendente
Premissa: pedido de exatamente R$ 500,00 tem frete grátis, compra de exatamente R$ 2.000,00 permite combinar formas de pagamento.
Motivo: o manual diz "acima de R$ 500,00" (grátis) e "abaixo de R$ 500,00" (R$ 35,00), sem cobrir o valor exato, e "acima de R$ 2.000,00" para a combinação. Na dúvida, a leitura favorável ao cliente.

### P-03 · Base dos limites de R$ 500 e R$ 2.000
ID: P-03
Seção: §5.1, §3.1, §6.2
Status: adotada
Teste: pendente
Premissa: os dois limites usam o valor dos produtos depois das promoções e antes do desconto PIX.
Motivo: o manual não define a base. O valor promocional é o preço de venda (§6.2), o PIX é uma forma de pagamento escolhida depois, e não deve tirar do cliente o frete grátis.

### P-04 · PIX em carrinho com itens promocionais
ID: P-04
Seção: §3, §6.2
Status: adotada
Teste: pendente
Premissa: num carrinho misto, os 5% do PIX incidem só sobre os itens sem promoção ativa.
Motivo: §6.2: "O desconto de PIX (5%) não se aplica sobre preços já promocionais", a regra é por item.

### P-05 · Arredondamento das parcelas
ID: P-05
Seção: §3.1
Status: adotada
Teste: pendente
Premissa: parcelas iguais truncadas ao centavo, o resto vai na primeira. R$ 459,90 em 12x = 1 × R$ 38,38 + 11 × R$ 38,32. O mínimo do §3.1 é verificado na menor parcela. Quando os valores diferem, o agente mostra os dois.
Motivo: o manual não define o arredondamento. Truncar e somar o resto na primeira fecha o total exato e é a prática comum de parcelamento.

### P-06 · Mínimo em até 3x
ID: P-06
Seção: §3.1
Status: adotada
Teste: pendente
Premissa: "sem valor mínimo de parcela (exceto abaixo de R$ 50,00)" = parcela mínima de R$ 50,00 em 2x e 3x. Em 1x não há mínimo.
Motivo: a frase se contradiz ("sem mínimo, exceto abaixo de R$ 50"), a única leitura que dá efeito à exceção é um mínimo de R$ 50.

### P-07 · Tabela de pagamento × §3.1
ID: P-07
Seção: §3, §3.1
Status: adotada
Teste: pendente
Premissa: vale o §3.1 (R$ 50 / R$ 80 / R$ 100 por faixa), não a "Parcela mínima de R$ 100,00" da tabela do §3.
Motivo: o §3.1 é a regra específica de parcelamento, a tabela resume a faixa mais alta.

### P-08 · Pedido parado
ID: P-08
Seção: — (o manual é omisso)
Status: adotada
Teste: pendente
Premissa: pedido em `pending` ou `confirmed` há mais de 5 dias úteis (P-20) → `situacao = parado`. O valor é configurável.
Motivo: os pedidos 9–16 estão abertos há meses sem previsão (`docs/data_quality_report.md`, A01). O agente precisa reconhecer o atraso em vez de dizer "está pendente".

### P-09 · Feriados e pontos facultativos
ID: P-09
Seção: §2
Status: a confirmar pela loja (calendário municipal de Campo Grande)
Teste: pendente
Premissa: feriados nacionais e de MS pela biblioteca `holidays`, e os de Campo Grande num YAML a conferir com o calendário oficial. Carnaval e Corpus Christi são pontos facultativos: o agente informa o horário normal e sugere confirmar pelo WhatsApp.
Motivo: o §2 fecha a loja "em feriados" sem listá-los, pontos facultativos não são feriados.

### P-10 · Datas especiais
ID: P-10
Seção: §2
Status: adotada
Teste: pendente
Premissa: não há dados de horário estendido. Na Black Friday de 2026 (sexta, 27/11), o agente informa o horário normal de sexta (9h às 18h) e diz que horários especiais são comunicados nas redes sociais e no WhatsApp. Caso de eval: "amanhã abrem até que horas?" perguntado na quinta, 26/11.
Motivo: o §2 diz que o horário "pode ser estendido" e que as alterações são comunicadas com antecedência, sem a comunicação, vale o horário regular.

### P-11 · Canal de venda
ID: P-11
Seção: §4.1
Status: adotada
Teste: pendente
Premissa: os pedidos não informam o canal, todos são tratados como compras online, e o direito de arrependimento (§4.1) se aplica.
Motivo: os pedidos têm rastreio e previsão de entrega, o que indica venda a distância, na dúvida, a leitura favorável ao cliente.

### P-12 · Região metropolitana de Campo Grande
ID: P-12
Seção: §5.1, §5.2
Status: a confirmar pela loja
Teste: pendente
Premissa: "região metropolitana" = clientes com cidade Campo Grande. As demais cidades dos dados (Dourados, Corumbá, Ponta Porã, Três Lagoas) seguem o §5.2.
Motivo: o manual não lista os municípios, nenhuma outra cidade dos dados fica na região de Campo Grande.

### P-13 · Contatos da loja
ID: P-13
Seção: §1.2, §7
Status: a confirmar pela loja
Teste: pendente
Premissa: WhatsApp (67) 3321-4500, do §7, a seção específica do canal. Telefone (67) 3341-4444, do §1.2 e da capa, **nunca chamado de WhatsApp**. E-mail `contato@emporiodamusica.com.br`, sem acento.
Motivo: o §1.2 diz "Telefone / WhatsApp (67) 3341-4444", e o §7 diz "O canal de WhatsApp (67) 3321-4500". O e-mail sem acento é o da capa, o acentuado (`empóriodamusica`) é outro domínio (IDN), e mensagens para ele provavelmente não chegam à loja.

### P-14 · Lojas parceiras
ID: P-14
Seção: §1, §7.1
Status: adotada
Teste: pendente
Premissa: nenhuma loja parceira é nomeada. Pedidos de acessórios são redirecionados com educação, sem indicar uma loja específica.
Motivo: o §7.1 diz "sugerir lojas parceiras quando possível", mas o manual e os dados não nomeiam nenhuma, inventar uma seria informação sem fonte.

### P-15 · "24 horas úteis"
ID: P-15
Seção: §7.3
Status: adotada
Teste: pendente
Premissa: "24 horas úteis" = horas com a loja aberta: seg–sex 9h–18h (9 h/dia), sáb 9h–13h (4 h), domingos e feriados não contam, Carnaval e Corpus Christi contam como dias normais (P-09). Fora do expediente, a contagem começa na próxima abertura. O agente informa o dia e a hora calculados ("até quarta, 10h"), nunca "24 horas úteis".
Motivo: é a leitura literal de "horas úteis" e a mais segura para a promessa ao cliente. Casos do teste: sex 17:00 → qua 10:00 (1 + 4 + 9 + 9 + 1), sáb 15:00 ou dom → começa seg 09:00 → qua 15:00, sáb 12:00 → qua 14:00, feriado no meio é pulado, Carnaval conta como dia normal.

### P-16 · Marco da troca por preferência
ID: P-16
Seção: §4.3
Status: adotada
Teste: pendente
Premissa: os 7 dias da troca por preferência contam a partir do recebimento, sujeitos ao estoque do produto desejado, consultado na hora.
Motivo: o §4.3 diz "em até 7 dias" sem marco, o recebimento é o marco do caso análogo (§4.1) e o único em que o cliente já pode avaliar o produto.

### P-17 · Fonte da data de recebimento
ID: P-17
Seção: §4.1, §4.3, §8.1
Status: adotada
Teste: pendente
Premissa: só uma fonte confiável (evento de entrega da transportadora) decide um prazo contado do recebimento. A previsão (`estimated_delivery`) e a data informada pelo cliente só encaminham o caso, a data informada vai para o ticket.
Motivo: o recebimento não está nos dados, as previsões contradizem o §5.1 (`docs/data_quality_report.md`, A02). Uma data informada ("recebi ontem") não pode conceder nem negar um direito.

### P-18 · Frete fora de Campo Grande
ID: P-18
Seção: §5.2
Status: adotada
Teste: pendente
Premissa: sem tabela de valores, o agente não informa um valor de frete para outras cidades. Diz que o frete é calculado pelo CEP, peso e dimensões, e que itens de grande porte podem exigir cotação individual.
Motivo: o §5.2 dá só prazos e modalidades, não há CEP nem tarifas nos dados.

### P-19 · Campanhas do §6.1
ID: P-19
Seção: §6.1, §7.3
Status: adotada
Teste: pendente
Premissa: as campanhas do §6.1 (como Black Friday "em todo o catálogo") só valem se houver promoção ativa no sistema para o produto.
Motivo: o §7.3 manda verificar se a promoção está ativa e nunca prometer desconto vencido, nenhuma promoção de Black Friday está ativa (`docs/data_quality_report.md`, A08).

### P-20 · "Dia útil" × "horas úteis"
ID: P-20
Seção: §3, §4.1, §5.1, §7.3
Status: adotada
Teste: pendente
Premissa: "dia útil" = segunda a sexta, sem feriados (compensação do boleto §3, reembolso §4.1, entrega §5.1, P-08). "Horas úteis" (P-15) = horas de loja aberta, **com sábado**. A diferença é intencional.
Motivo: "dia útil" tem o sentido usual bancário e de prazos, "horas úteis" de atendimento segue o horário da loja (§2), que abre no sábado.

### P-21 · Itens não elegíveis (§4.4) sem dados
ID: P-21
Seção: §4.4
Status: adotada
Teste: pendente
Premissa: os dados não dizem se houve setup sob encomenda nem aviso de "venda final". O agente pergunta ao cliente e, se a resposta for sim, encaminha à equipe. A exclusão de boquilhas não tem efeito enquanto as categorias 6 e 7 (sopros) estiverem vazias.
Motivo: negar a troca sem dado seria uma decisão sem fonte confiável, ignorar o §4.4 seria conceder um direito que o manual exclui.
