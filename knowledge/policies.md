# Manual de Políticas e Procedimentos — Empório da Música

Transcrição de `data/policies.pdf`

- Cada seção `## <ID> <Título>` corresponde a uma seção do manual. O ID é a numeração do manual (`4.1`, `8.1`, etc) e é o que `consultar_politica` recebe.
- O texto do manual está em citação (`>`), sem alterações, inclusive typos.
- Fora da citação ficam as **anotações**: 
    `Marco` (de onde conta o prazo)
    `Premissas` (IDs em [`docs/assumptions.md`](../docs/assumptions.md)).
- Regra de conflito: 
    onde há premissa, ela prevalece sobre a leitura literal; anotações não são texto do manual.

**Capa do manual** (sem numeração):

> EMPÓRIO DA MÚSICA — Sua música começa aqui.
> MANUAL DE POLÍTICAS E PROCEDIMENTOS — Atendimento ao Cliente
> Rua 14 de Maio, 3200 — Centro, Campo Grande – MS – CEP 79202-333
> (67) 3341-4444 — contato@emporiodamusica.com.br
> Versão 2.1 — Junho de 2025. Documento interno — Uso restrito da equipe de atendimento

## 1 Sobre a Empório da Música

Página 2.

> A Empório da Música é uma loja especializada em instrumentos musicais, fundada em 2008 em Campo
> Grande, Mato Grosso do Sul. Com mais de 15 anos de atuação no mercado, somos referência regional
> na venda de instrumentos para músicos iniciantes, intermediários e profissionais.
>
> Nosso catálogo abrange mais de 300 instrumentos de marcas nacionais e internacionais, incluindo
> guitarras, baixos, violões, baterias, teclados, instrumentos de sopro, cordas orquestrais e
> ukuleles.
>
> Trabalhamos exclusivamente com instrumentos musicais — não comercializamos acessórios como
> cordas, palhetas, cabos, cases, pedais ou amplificadores.

**Premissas:** P-14.

## 1.1 Missão

Página 2.

> Democratizar o acesso a instrumentos musicais de qualidade na região Centro-Oeste, oferecendo
> atendimento especializado e preços competitivos, contribuindo para o desenvolvimento cultural e
> musical da comunidade.

## 1.2 Dados da Empresa

Página 2.

> | Campo | Informação |
> |---|---|
> | Razão Social | Empório da Música Instrumentos Musicais Ltda. |
> | Nome Fantasia | Empório da Música |
> | CNPJ | 12.345.678/0001-90 |
> | Endereço | Rua 14 de Maio, 3200 — Centro, Campo Grande - MS, 79202-333 |
> | Telefone / WhatsApp | (67) 3341-4444 |
> | E-mail | contato@empóriodamusica.com.br |
> | Fundação | 2008 |

**Premissas:** P-13. O manual se contradiz: o §7 dá outro número de WhatsApp, e o e-mail aqui está
acentuado, ao contrário da capa.

## 2 Horário de Funcionamento

Página 2.

> O atendimento presencial na loja segue os horários abaixo. O atendimento via WhatsApp segue o
> mesmo horário, com respostas automáticas fora do expediente.
>
> | Dia | Horário |
> |---|---|
> | Segunda a Sexta-feira | 09:00 às 18:00 |
> | Sábado | 09:00 às 13:00 |
> | Domingo e Feriados | Fechado |
>
> Em datas especiais (Black Friday, Aniversário da Loja, Natal), o horário pode ser estendido.
> Alterações serão comunicadas com antecedência nas redes sociais e no atendimento via WhatsApp.

**Premissas:** P-09, P-10, P-15, P-20.

## 3 Formas de Pagamento

Página 3.

> Aceitamos as seguintes formas de pagamento para compras presenciais e online:
>
> | Forma | Condições | Observações |
> |---|---|---|
> | PIX | Pagamento à vista | 5% de desconto sobre o preço de tabela |
> | Cartão de Débito | Pagamento à vista | Todas as bandeiras aceitas |
> | Cartão de Crédito | Até 12x sem juros | Parcela mínima de R$ 100,00 |
> | Boleto Bancário | Pagamento à vista | Compensação em até 3 dias úteis |

**Marco:** boleto compensado em até 3 dias úteis a partir do pagamento (dia útil: P-20).
**Premissas:** P-04, P-07, P-20, P-22.

## 3.1 Regras de Parcelamento

Página 3.

> - Parcelamento em até 3x: sem juros, sem valor mínimo de parcela (exceto abaixo de R$ 50,00).
> - Parcelamento de 4x a 6x: sem juros, parcela mínima de R$ 80,00.
> - Parcelamento de 7x a 12x: sem juros, parcela mínima de R$ 100,00.
> - Combinação de formas de pagamento: permitida (ex.: PIX + cartão) para compras acima de
>   R$ 2.000,00.

**Premissas:** P-02, P-03, P-05, P-06, P-07, P-23.

## 4 Política de Trocas e Devoluções

Página 4.

> A Empório da Música segue as diretrizes do Código de Defesa do Consumidor (Lei nº 8.078/90) e
> oferece condições claras para trocas e devoluções.

**Premissas:** P-11, P-17.

## 4.1 Direito de Arrependimento (Compras Online)

Página 4.

> - O cliente pode solicitar a devolução em até 7 (sete) dias corridos após o recebimento do
>   produto, sem necessidade de justificativa.
> - O produto deve estar em sua embalagem original, sem sinais de uso, com todos os acessórios e
>   manuais.
> - O reembolso será realizado na mesma forma de pagamento original em até 10 dias úteis.
> - O frete de devolução é por conta da loja em caso de arrependimento.

**Marco:** 7 dias corridos a partir do **recebimento** (fonte confiável: P-17). Reembolso em até 10
dias úteis (P-20).
**Premissas:** P-11, P-17, P-20.

## 4.2 Trocas por Defeito

Página 4.

> - Produtos com defeito de fabricação podem ser trocados em até 30 (trinta) dias corridos após a
>   compra.
> - Após os 30 dias, o cliente deve acionar a garantia diretamente com o fabricante. A Empório da
>   Música pode intermediar o processo mediante solicitação.
> - Danos causados por mau uso, quedas, exposição a umidade excessiva ou modificações não
>   autorizadas não são cobertos.

**Marco:** 30 dias corridos a partir da **compra** (`order_date`, confiável).
**Premissas:** P-01. "Após os 30 dias… diretamente com o fabricante" não se aplica enquanto houver
garantia legal (§8.1).

## 4.3 Trocas por Preferência

Página 4.

> - Trocas por preferência (cor, modelo, tamanho) são permitidas em até 7 dias, mediante
>   disponibilidade do produto desejado.
> - O produto deve estar em perfeito estado e na embalagem original.
> - Diferenças de valor serão cobradas ou reembolsadas conforme o caso.

**Marco:** 7 dias a partir do **recebimento**. O manual não diz o marco; a escolha é a P-16.
**Premissas:** P-16, P-17.

## 4.4 Itens Não Elegíveis para Troca

Página 4.

> - Instrumentos com personalização ou ajustes sob encomenda (setup, regulagem especial).
> - Produtos adquiridos em promoções de liquidação com aviso explícito de "venda final".
> - Boquilhas de instrumentos de sopro, por questões de higiene.

**Premissas:** P-21.

## 5 Política de Frete e Entregas

Página 4. Seção sem texto próprio no manual: ver 5.1 a 5.3.

## 5.1 Entregas na Região Metropolitana de Campo Grande

Página 4.

> - Frete grátis para pedidos acima de R$ 500,00.
> - Para pedidos abaixo de R$ 500,00, taxa fixa de R$ 35,00.
> - Prazo de entrega: 1 a 3 dias úteis.
> - Entrega realizada por motoboy próprio. O cliente será contactado por telefone antes da
>   entrega.

**Marco:** 1 a 3 dias úteis (P-20). O manual não diz quando o prazo começa.
**Premissas:** P-02, P-03, P-12, P-20, P-23.

## 5.2 Entregas para Outras Cidades

Páginas 4–5.

> Utilizamos os serviços dos Correios (PAC e SEDEX) e da transportadora Jadlog para envios fora da
> região metropolitana de Campo Grande.
>
> | Modalidade | Prazo Estimado | Rastreamento | Seguro |
> |---|---|---|---|
> | PAC (Correios) | 5 a 12 dias úteis | Sim | Incluído |
> | SEDEX (Correios) | 2 a 5 dias úteis | Sim | Incluído |
> | Jadlog (.package) | 3 a 8 dias úteis | Sim | Incluído |
>
> O valor do frete é calculado automaticamente com base no CEP de destino, peso e dimensões do
> produto. Instrumentos de grande porte (baterias acústicas, pianos digitais, contrabaixos) podem
> exigir frete especial com cotação individual.
>
> Todos os envios incluem seguro contra extravios e danos durante o transporte. Em caso de avaria,
> o cliente deve recusar o recebimento e entrar em contato imediatamente com a loja.

**Premissas:** P-12, P-18.

## 5.3 Código de Rastreamento

Página 5.

> O código de rastreamento é enviado automaticamente por e-mail e WhatsApp assim que o pedido é
> despachado. O formato padrão é BR seguido de 9 caracteres alfanuméricos e BR (exemplo:
> BR4K7M2X9P1BR). O rastreamento pode ser consultado diretamente no site dos Correios ou da
> Jadlog.

## 6 Promoções e Descontos

Página 6. Seção sem texto próprio no manual: ver 6.1 e 6.2.

## 6.1 Tipos de Promoção

Página 6.

> A Empório da Música realiza promoções periódicas ao longo do ano. As principais campanhas
> incluem:
>
> - Aniversário da Loja (Agosto): descontos de 10% a 25% em itens selecionados.
> - Black Friday (Novembro): descontos de 15% a 30% em todo o catálogo.
> - Volta às Aulas (Fevereiro): descontos especiais em instrumentos para estudantes.
> - Queima de Estoque: promoções pontuais para renovação de catálogo.
> - Semana do Músico: promoções na semana do Dia do Músico (22 de novembro).

**Premissas:** P-10, P-19, P-22.

## 6.2 Regras de Promoções

Página 6.

> **Cumulatividade:** promoções não são cumulativas. O desconto de PIX (5%) não se aplica sobre
> preços já promocionais.
>
> **Estoque:** promoções estão sujeitas à disponibilidade de estoque. Produtos esgotados durante a
> promoção não geram direito a rain check (reserva de preço).
>
> **Comunicação:** preços promocionais devem sempre ser apresentados junto ao preço original e o
> percentual de desconto, para total transparência ao cliente.

**Premissas:** P-03, P-04, P-22.

## 7 Atendimento via WhatsApp

Página 6.

> O canal de WhatsApp (67) 3321-4500 é o principal meio de atendimento remoto da Empório da
> Música. O atendimento pode ser realizado por atendentes humanos ou pelo assistente virtual.

**Premissas:** P-13.

## 7.1 Diretrizes de Atendimento

Página 6.

> **Tom de voz:** informal mas profissional. O cliente deve se sentir acolhido, como se estivesse
> conversando com um amigo que entende de música. Evitar linguagem excessivamente formal ou
> robotizada.
>
> **Tempo de resposta:** máximo de 5 minutos durante o horário de funcionamento. Fora do
> expediente, o assistente virtual deve informar o horário de retorno.
>
> **Informações precisas:** nunca fornecer informações sobre preços, estoque ou prazos sem
> consultar o sistema. Informações incorretas geram frustração e podem configurar propaganda
> enganosa.
>
> **Escopo:** o atendente deve informar que a loja trabalha exclusivamente com instrumentos
> musicais. Pedidos de acessórios (cordas, cabos, palhetas, pedais, amplificadores, cases) devem
> ser educadamente redirecionados. Sugerir lojas parceiras quando possível.

**Premissas:** P-14.

## 7.2 Fluxo de Atendimento Padrão

Páginas 6–7.

> 1. Saudação: cumprimentar o cliente pelo nome (se disponível) e perguntar como pode ajudar.
> 2. Entendimento: identificar a necessidade do cliente (busca de produto, dúvida, rastreamento,
>    reclamação).
> 3. Consulta: buscar no sistema as informações relevantes (produto, estoque, promoção, pedido).
> 4. Resposta: apresentar as opções de forma clara e objetiva, com preços e condições.
> 5. Fechamento: confirmar se o cliente precisa de mais alguma coisa e encerrar com cordialidade.

## 7.3 Situações Especiais

Página 7.

> **Produto fora de estoque:** informar que o produto está temporariamente indisponível e sugerir
> alternativas semelhantes que estejam disponíveis. Nunca confirmar disponibilidade sem verificar
> o estoque atual.
>
> **Produto descontinuado:** informar que o produto não faz mais parte do catálogo e oferecer
> modelos equivalentes ou sucessores.
>
> **Promoção expirada:** caso o cliente pergunte sobre uma promoção, verificar se ela encontra-se
> ativa no sistema. Se a promoção estiver vencida, informar com transparência e apresentar o preço
> atual. Nunca prometer um desconto que não está mais vigente.
>
> **Reclamação:** ouvir o cliente com empatia, registrar a reclamação e encaminhar para o
> responsável. Prazo de retorno: 24 horas úteis.

**Marco:** retorno da reclamação em 24 horas úteis a partir do registro, contadas em horas de loja
aberta (P-15). O agente informa o dia e a hora calculados.
**Premissas:** P-15, P-19.

## 8 Garantia

Página 7. Seção sem texto próprio no manual: ver 8.1 a 8.3.

## 8.1 Garantia Legal

Página 7.

> Conforme o Código de Defesa do Consumidor, todos os produtos possuem garantia legal de 90
> (noventa) dias contra defeitos de fabricação, contados a partir da data de recebimento pelo
> cliente.

**Marco:** 90 dias a partir do **recebimento** (fonte confiável: P-17).
**Premissas:** P-01, P-17.

## 8.2 Garantia do Fabricante

Página 7.

> Além da garantia legal, a maioria dos fabricantes oferece garantia própria que pode variar de 6
> meses a 2 anos. Os prazos e condições específicos estão detalhados no certificado de garantia
> que acompanha cada produto.

**Marco:** prazo do certificado de cada produto (de 6 meses a 2 anos); não está nos dados.
**Premissas:** P-01.

## 8.3 O que Não Cobre a Garantia

Página 7.

> - Desgaste natural de peças (trastes, cordas, feltros, palhetas de sopro).
> - Danos por mau uso, queda, exposição a condições climáticas extremas.
> - Modificações ou reparos realizados por terceiros não autorizados.
> - Danos estéticos que não afetem a funcionalidade do instrumento.

## 9 Privacidade e Proteção de Dados

Páginas 7–8.

> A Empório da Música está em conformidade com a Lei Geral de Proteção de Dados (LGPD — Lei nº
> 13.709/2018). Os dados pessoais coletados durante o atendimento (nome, telefone, e-mail,
> endereço) são utilizados exclusivamente para:
>
> - Processamento e entrega de pedidos.
> - Comunicação sobre status de pedidos e rastreamento.
> - Envio de promoções e novidades (mediante consentimento explícito do cliente).
> - Cumprimento de obrigações legais e fiscais.
>
> Dados de clientes não são compartilhados com terceiros para fins de marketing. O cliente pode
> solicitar a exclusão de seus dados a qualquer momento entrando em contato pelo WhatsApp ou
> e-mail.

## 10 Disposições Finais

Página 8.

> Este manual é um documento interno da Empório da Música e deve ser utilizado como referência por
> todos os membros da equipe de atendimento, incluindo o assistente virtual. As políticas descritas
> neste documento estão sujeitas a atualizações periódicas.
>
> Em caso de dúvidas sobre a aplicação de qualquer política, o atendente deve consultar a gerência
> antes de fornecer informações ao cliente. O objetivo é sempre garantir transparência, precisão e
> a melhor experiência possível para o cliente.
