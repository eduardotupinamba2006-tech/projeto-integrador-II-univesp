# Documentação da implementação

Sistema de emissão de certidões sacramentais e gestão de dízimo paroquial.
Projeto Integrador II, UNIVESP.

Este documento descreve o que está implementado na branch `feature/sistema-completo`, como cada parte funciona e como rodar e testar o sistema. As decisões que mudaram o Plano de Ação original estão registradas, com data e motivo, em [`DECISOES.md`](../DECISOES.md). O que ainda falta fazer está no fim deste documento.

## Visão geral

O sistema atende três tipos de usuário. O fiel (papel `publico`) cria a própria conta, pede certidões e contribui com o dízimo. A secretaria da paróquia (papel `paroquial`) analisa os pedidos, mantém o livro de registros sacramentais em formato digital e acompanha a arrecadação da própria paróquia. A chancelaria da diocese (papel `diocesano`) consulta os números de todas as paróquias da diocese, sem poder alterar nada.

A regra central é que a certidão sai sempre do registro oficial da paróquia, nunca do que o fiel digitou no pedido. O fiel informa o que lembra do sacramento, a paróquia procura o registro no livro, e o PDF é gerado no servidor a partir desse registro.

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Páginas | HTML, CSS e JavaScript puro, sem framework e sem etapa de build |
| Funções de servidor | Python, como funções serverless da Vercel |
| Banco, login e arquivos | Supabase (Postgres com Row Level Security, Auth e Storage) |
| Pagamento | Pix pela API de Orders do Mercado Pago (sandbox) |
| Email | Resend |
| Geração de PDF | `fpdf2` e `segno` (QR Code) |
| Testes | Vitest, pytest, Playwright com axe-core |
| Integração contínua | GitHub Actions |

O Plano de Ação entregue à orientadora previa Next.js com TypeScript. A equipe trocou para HTML, CSS e JavaScript puro porque os integrantes têm níveis de experiência diferentes e o escopo do sistema não precisava da complexidade de um framework. A decisão está registrada na seção 1 do `DECISOES.md`.

## Estrutura de pastas

```
index.html              página inicial
pages/                  demais páginas (login, certidão, dízimo, painéis, validação)
css/                    estilo.css (comum) e dashboard-diocese.css
js/                     módulos do navegador
js/lib/                 funções puras (validação, formatação, distância, somas)
js/paginas/             script de cada página
fonts/                  fonte Outfit e sua licença
img/                    fotos do site (ver img/LEIAME.md)
api/                    funções Python da Vercel
api/_lib/               código compartilhado entre as funções
supabase/migrations/    schema do banco, versionado
supabase/seed.sql       dados sintéticos para desenvolvimento e testes
scripts/servidor_dev.py servidor local de desenvolvimento
tests/vitest/           testes de JavaScript
tests/pytest/           testes das funções Python e da RLS
tests/e2e/              testes de ponta a ponta e de acessibilidade
.github/workflows/      integração contínua
```

## Banco de dados

O schema fica em duas migrations, em `supabase/migrations/`.

A primeira (`20260929120000_schema_inicial.sql`) cria as nove tabelas do modelo de dados oficial: `dioceses`, `paroquias`, `perfis`, `registros_sacramentais`, `pagamentos`, `dizimistas`, `doacoes`, `solicitacoes_certidao` e `emails_enviados`. As colunas seguem exatamente a especificação. O projeto Supabase de produção tinha uma versão dessas tabelas criada à mão, com ids numéricos e tipos enum, sem políticas de acesso e sem nenhum dado. A migration apaga essa versão e recria tudo a partir da especificação.

A segunda (`20260930120000_storage_e_webhooks_email.sql`) cria o bucket privado de certidões e os gatilhos que disparam os emails.

### Controle de acesso (RLS)

Toda tabela tem Row Level Security ativada. As permissões ficam no banco, não no código das páginas, então valem mesmo para quem tentar acessar a API do Supabase diretamente.

| Tabela | Fiel | Paróquia | Diocese |
|---|---|---|---|
| `perfis` | lê e edita o próprio perfil | lê o próprio | lê o próprio |
| `registros_sacramentais` | sem acesso | lê, cria, edita e apaga os da própria paróquia | lê os das paróquias da diocese |
| `solicitacoes_certidao` | cria e lê os próprios pedidos | lê os da paróquia e rejeita | lê os da diocese |
| `pagamentos` | lê os próprios | lê os da paróquia | lê os da diocese |
| `dizimistas` | cadastra a si mesmo e lê o próprio cadastro | lê os da paróquia | lê os da diocese |
| `doacoes` | lê as próprias | lê as da paróquia | lê as da diocese |
| `emails_enviados` | sem acesso | sem acesso | sem acesso |
| `dioceses`, `paroquias` | leitura pública, inclusive sem login | leitura | leitura |

Aplicada ao pé da letra, a regra geral de que cada papel "lê e edita as próprias linhas" deixaria um fiel marcar o próprio pagamento como pago ou mudar o próprio papel para diocesano. Por isso a escrita ficou mais restrita que a leitura:

- pagamentos e doações só são gravados pelo servidor;
- ninguém altera o próprio papel, paróquia ou diocese;
- o fiel só corrige os dados do pedido antes de pagar;
- a paróquia rejeita pedidos diretamente, mas a aprovação passa pela função que gera o PDF.

Essas travas são triggers que conferem quais colunas mudaram. As funções auxiliares ficam num schema chamado `privado`, que a API não expõe. A seção 3 do `DECISOES.md` detalha essa decisão.

Quando alguém cria uma conta no Supabase Auth, um trigger cria automaticamente o perfil com papel `publico`, usando o nome e o CPF informados no cadastro. Contas de paróquia e de diocese são criadas por um administrador, que depois ajusta o papel no banco.

### Dados sintéticos

O arquivo `supabase/seed.sql` cria duas dioceses, três paróquias e sete contas de teste, além de registros sacramentais, pagamentos, um dizimista e uma solicitação já paga na fila. Todos os nomes, CPFs e endereços são inventados. Convicção religiosa é dado sensível pela LGPD (art. 5º, II), e nenhum dado real de paroquiano entra em nenhum ambiente.

As contas de teste usam a senha `SenhaTeste#2026`:

| Email | Papel |
|---|---|
| `fiel1@teste.local`, `fiel2@teste.local` | fiel |
| `paroquia.a1@teste.local` | Paróquia São Exemplo (Diocese Alfa) |
| `paroquia.a2@teste.local` | Paróquia Santa Amostra (Diocese Alfa) |
| `paroquia.b1@teste.local` | Paróquia Nossa Senhora do Teste (Diocese Beta) |
| `diocese.alfa@teste.local`, `diocese.beta@teste.local` | diocese |

## Funções de servidor

As funções ficam em `api/`. Cada arquivo vira um endpoint na Vercel. Elas chamam o Supabase, o Mercado Pago e o Resend pela biblioteca padrão do Python (`urllib`), sem SDKs, e usam a chave de serviço do Supabase. Como essa chave ignora a RLS, cada função confere por conta própria quem está chamando e o que essa pessoa pode fazer.

| Endpoint | O que faz |
|---|---|
| `POST /api/cobranca_pix` | Gera a cobrança Pix de uma taxa de certidão ou de um dízimo. A taxa é fixa em R$ 30,00, definida no servidor, e o valor enviado pelo navegador é ignorado. O dízimo é cobrado pelo valor integral, entre R$ 1,00 e R$ 100.000,00. Se o pedido já tem uma cobrança pendente, a função devolve a mesma cobrança em vez de criar outra. No sandbox, o Pix vai com o comprador de teste e é aprovado sozinho em alguns segundos. |
| `POST /api/webhook_pagamento` | Recebe a notificação de order do Mercado Pago. Confere a assinatura `x-signature` e consulta a order na API do Mercado Pago antes de mudar qualquer coisa. Confere também o valor e o id da transação. Com o pagamento aprovado, marca `pagamentos` como pago. Se for uma taxa, move o pedido para "em análise"; se for um dízimo de um dizimista cadastrado, cria a doação. Notificações repetidas não duplicam nada. |
| `POST /api/pdf` | Usada pela secretaria da paróquia. Confere se o pedido é da paróquia dela, se está em análise e se o registro escolhido é do mesmo sacramento e da mesma paróquia. Gera o PDF a partir do registro oficial, grava no bucket `certidoes` e marca o pedido como aprovado. |
| `GET /api/validar_qrcode?c=...` | Endpoint público de autenticidade. O código do QR é o id do pedido mais uma assinatura HMAC-SHA256. A função devolve se a certidão é válida e, nesse caso, o sacramento, o nome, a data, a paróquia, a diocese e a data de emissão. |
| `POST /api/enviar_email` | Chamada pelos gatilhos do banco. Escolhe o email certo, envia pelo Resend e grava toda tentativa em `emails_enviados`, com sucesso ou falha. |
| `GET /api/config` | Entrega ao navegador a URL do Supabase e a chave pública do ambiente. Como não há etapa de build, é assim que o preview e a produção apontam cada um para o seu próprio projeto. |

As funções `cobranca_pix` e `config` não estavam na lista original de funções. A cobrança Pix precisa do token secreto do Mercado Pago e por isso não pode ser gerada no navegador. A configuração existe porque não há build para injetar variáveis nas páginas.

### Certidão em PDF

O PDF tem o cabeçalho da diocese e da paróquia, o título do sacramento e o texto da certidão com nome e data por extenso. Traz também livro, folha, número, celebrante e padrinhos (ou testemunhas, no casamento), a data de emissão e o QR Code com o link de validação. O arquivo fica em `certidoes/{id do solicitante}/{id do pedido}.pdf`. Só o próprio solicitante consegue baixá-lo, por link assinado.

### Emails

| Evento | Como é enviado |
|---|---|
| Conta criada | Supabase Auth, com o Resend como SMTP |
| Esqueci a senha | Supabase Auth, com o Resend como SMTP |
| Pagamento criado | gatilho no banco, texto diferente para dízimo e para taxa |
| Dízimo pago | gatilho no banco, recibo da doação |
| Taxa de certidão paga | gatilho no banco, aviso de pedido em análise |
| Certidão aprovada | gatilho no banco, com link do PDF válido por 7 dias |
| Certidão rejeitada | gatilho no banco, com o motivo escrito pela paróquia |

Os gatilhos leem a URL da função e um segredo compartilhado do Vault do Supabase. Cada ambiente tem os seus valores, e nada disso fica no repositório. Sem esses segredos, como no Supabase local do CI, os gatilhos não fazem nada.

## Páginas

| Página | Quem usa | Conteúdo |
|---|---|---|
| `index.html` | todos | apresentação dos serviços e passo a passo do pedido |
| `pages/cadastro.html` | visitante | criação de conta, com validação de CPF e senha |
| `pages/entrar.html` | todos | login; cada papel vai para a sua página inicial |
| `pages/recuperar-senha.html`, `pages/nova-senha.html` | todos | recuperação de senha por email |
| `pages/solicitar-certidao.html` | fiel | escolha do sacramento e da paróquia, dados lembrados e geração do Pix |
| `pages/minhas-solicitacoes.html` | fiel | situação de cada pedido, novo Pix, download do PDF e motivo de rejeição |
| `pages/dizimo.html` | fiel | escolha da paróquia, valor, cadastro opcional como dizimista e Pix |
| `pages/painel-paroquial.html` | paróquia | fila de pedidos, análise com busca no livro, vínculo ou rejeição, cadastro de registros e arrecadação mensal |
| `pages/dashboard-diocese.html` | diocese | totais da diocese, certidões e arrecadação por paróquia e por mês |
| `pages/validar.html` | qualquer pessoa | resultado da leitura do QR Code |

A escolha de paróquia aparece na certidão e no dízimo. Ela busca por nome ou endereço, ignorando acentos, e ordena as paróquias pela distância até o usuário, usando a localização do navegador. A distância é calculada pela fórmula de Haversine, em `js/lib/geo.js`. Com a chave do Google Maps configurada (`GOOGLE_MAPS_API_KEY`), aparecem também a busca a partir de um endereço ou CEP, feita pela geocodificação do Google, e um mapa com um marcador por paróquia. Clicar num marcador escolhe a paróquia, e escolher na lista destaca o marcador. Sem a chave, ou se o Google recusar a chave, o mapa some e a lista continua funcionando.

O cliente do Supabase é carregado por CDN, com a versão fixada. As páginas protegidas mandam quem não está logado para o login e, depois de entrar, trazem a pessoa de volta para onde ela estava. Esse retorno só aceita endereços internos do site, para não ser usado como redirecionamento para sites externos.

### Acessibilidade

As páginas usam HTML semântico, com cabeçalho, navegação, conteúdo principal e rodapé marcados. Todo campo tem rótulo visível. As mensagens de erro ficam ligadas ao campo por `aria-describedby`, e os avisos de status são anunciados pelo leitor de tela com `aria-live`. Há um link para pular direto ao conteúdo, o foco do teclado fica sempre visível e os alvos de toque têm pelo menos 44 px. O teste automático com axe-core roda em todas as páginas e nos dois modos de cor. O widget VLibras aparece em todas as páginas, como um botão fixo na lateral direita. O cabeçalho, o rodapé e o VLibras são componentes únicos (`<site-cabecalho>` e `<site-rodape>`, em `js/layout.js`), usados por todas as páginas.

### Identidade visual

O visual segue a linha de um serviço institucional sóbrio, pensado para paroquianos de todas as idades. A cor de destaque é o azul-cobalto (`#1e3a8a`) que a equipe já usava no primeiro protótipo do painel diocesano, sobre tons neutros frios. O site acompanha o modo claro ou escuro do sistema do usuário.

A fonte é a Outfit, com licença livre (OFL), hospedada no próprio projeto para não depender do Google em produção. Os ícones são da biblioteca Phosphor. As animações se limitam a transições curtas e a uma entrada suave do conteúdo, e ficam desligadas para quem ativa a opção de reduzir movimento no sistema.

As fotos ficam em `img/`. O arquivo [`img/LEIAME.md`](../img/LEIAME.md) diz quais fotos entram em cada espaço e o que evitar. Enquanto uma foto não existir, aparece um fundo azul no lugar.

## Testes

| Suíte | Quantidade | O que cobre | Onde roda |
|---|---|---|---|
| pytest, RLS | 156 | isolamento entre papéis, paróquias e dioceses em todas as tabelas, travas de coluna, bucket de certidões e gatilhos de email | CI, contra um Supabase local |
| pytest, funções | 68 | cobrança Pix, webhook, assinatura do Mercado Pago, geração do PDF, token do QR Code, validação pública e escolha e envio de emails, com Supabase, Mercado Pago e Resend simulados | CI |
| Vitest | 35 | validação de CPF, email, senha e valor; formatação de moeda e data; distância e ordenação de paróquias; somas de arrecadação | CI |
| Playwright | 27 | login por papel, páginas protegidas, painéis, fluxo completo de certidão (vínculo, PDF, download, QR Code e rejeição) e acessibilidade com axe-core em 11 páginas nos modos claro e escuro | localmente, contra o Supabase de desenvolvimento |

Os testes de RLS abrem uma transação, criam os próprios dados, simulam cada papel e desfazem tudo no fim. Assim, não dependem do seed. Quando o banco não está disponível, eles são pulados localmente, mas falham no CI, para que o CI nunca fique verde sem ter testado de verdade.

No teste de ponta a ponta da certidão, o pagamento entra como dado semeado pelo próprio teste, para não depender do Mercado Pago. O fluxo testado começa com o pedido já pago e vai até a validação do QR Code. O Pix real do sandbox, aprovado automaticamente, foi conferido à parte no site publicado.

## Integração contínua

O workflow `.github/workflows/ci.yml` roda a cada push e em pull requests, com três jobs em paralelo:

1. **Banco de dados:** sobe o Supabase local com a CLI, aplica as migrations e o seed e roda os testes de RLS.
2. **Funções Python:** roda os testes das funções.
3. **Frontend:** roda o Vitest.

Os testes Playwright ainda não estão no CI. Eles vão rodar contra o preview da Vercel quando o deploy estiver configurado.

## Ambientes

| Ambiente | Onde fica | Para que serve |
|---|---|---|
| Local | `py scripts/servidor_dev.py`, em `http://localhost:3000` | desenvolvimento e testes Playwright |
| Supabase de desenvolvimento | projeto `certidoes-dev` (`uqrnudzczbnkhxlcurhr`) | banco usado pelo ambiente local, já com as migrations e o seed aplicados |
| Supabase de produção | projeto `lsunsrdrkaywocdcvbxu` | produção e demonstração; ainda tem as tabelas antigas, criadas à mão |
| CI | Supabase local dentro do GitHub Actions | testes de banco |

O plano era desenvolver com o Supabase local via Docker. O computador de desenvolvimento não tem virtualização disponível, então os testes de banco rodam no CI e o desenvolvimento local usa o projeto `certidoes-dev`.

As chaves ficam fora do repositório. Localmente elas ficam em `.env.local`, que o git ignora. Na Vercel, ficam no painel de variáveis de ambiente. O arquivo `.env.example` lista os nomes das variáveis, sem valores.

### Como rodar localmente

1. Instale as dependências:
   ```
   npm ci
   py -m pip install -r requirements.txt -r requirements-dev.txt
   npx playwright install chromium
   ```
2. Crie o `.env.local` a partir do `.env.example` com as chaves do projeto `certidoes-dev`.
3. Suba o servidor com `py scripts/servidor_dev.py` e acesse `http://localhost:3000`.
4. Rode os testes:
   ```
   npx vitest run
   py -m pytest tests/pytest -m "not rls"
   npx playwright test
   ```

Os testes de RLS (`py -m pytest tests/pytest -m rls`) precisam de um Supabase local com Docker, ou podem ser acompanhados pelo CI.

## Critérios de aceite

| Critério | Situação |
|---|---|
| Migrations aplicadas e RLS isolando os três papéis | feito e testado no CI e no projeto de desenvolvimento; falta aplicar em produção |
| Cadastro, login e recuperação de senha | páginas prontas e testadas; o email de recuperação depende do SMTP do Resend |
| Busca de paróquia por proximidade | feita com a localização do navegador e, com a chave configurada, com endereço ou CEP e mapa do Google |
| Fluxo completo de certidão até o PDF com QR Code | testado de ponta a ponta a partir do pedido pago; falta o Pix sandbox real |
| Validação do QR Code para certidão válida e inválida | feito e testado |
| Fluxo completo de dízimo até a arrecadação | lógica pronta e testada com simulação; falta o Pix sandbox real |
| Painéis paroquial e diocesano com a RLS respeitada | feito e testado |
| Sete emails em sandbox com registro em `emails_enviados` | lógica e registro testados; falta configurar o Resend |
| VLibras em todas as páginas, sem violação nova no axe-core | feito: widget oficial em todas as páginas, com teste de presença e axe-core sem violações |
| Vitest, pytest e Playwright passando localmente e no CI | passam localmente; o Playwright ainda não está no CI |
| GitHub Actions rodando a suíte a cada push | roda banco, funções e Vitest; falta o Playwright |
| produção publicada e testada (27 testes Playwright contra o site); preview ainda sem variáveis |
| `DECISOES.md` com a mudança de stack | feito |

## O que falta

As integrações externas dependem de contas e chaves que a equipe precisa criar. Ninguém deve colocar essas chaves no repositório nem mandá-las por chat.

- Mercado Pago: Access Token de produção da conta de vendedor de teste, o segredo de assinatura do webhook (evento "Order (Mercado Pago)") e `MP_EMAIL_PAGADOR_TESTE` com o email de uma conta compradora de teste.
- Resend: chave da API, configuração como SMTP do Supabase Auth e remetente.
- Google Maps: cadastrar `GOOGLE_MAPS_API_KEY` na Vercel. A chave precisa das APIs Maps JavaScript e Geocoding e fica restrita ao domínio do site.
- Vercel: cadastrar as variáveis de ambiente também no Preview e colocar o Playwright no CI contra o preview.
- Produção: aplicar as migrations no projeto de produção e cadastrar os segredos do Vault para os emails.
- Fotos: confirmar a licença das imagens em `img/` antes de publicar e, se preciso, dar o crédito no rodapé.
