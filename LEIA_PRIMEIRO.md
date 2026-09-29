# Atualização 0.7.1
Leia CORRECAO_VOZ_071.md para o fluxo de vozes corrigido.

# MontaVideo 0.7 — áudio, cenas físicas e montagem editável

## Abrir e atualizar

Extraia a pasta MontaVideo do ZIP. Feche a versão anterior e execute INICIAR.bat.
Na primeira execução ele prepara o Python e as dependências; requer internet.
Se a janela desktop falhar, o programa tenta abrir automaticamente no navegador.
INICIAR_NAVEGADOR.bat também está disponível. Ambos executam o backend NO SEU PC.
Não há upload do material para um servidor do MontaVideo.

Pode instalar em uma pasta nova. Conexões, lista de projetos, preferências, modelos
novos e cache ficam no perfil Windows em %LOCALAPPDATA%\MontaVideo. As chaves são
protegidas com DPAPI para seu usuário. As chaves já salvas na versão 0.6 são lidas.
O campo vazio com “Salva neste computador” significa que a chave foi preservada.
O token do Drift pode expirar quando o editor encerrar a sessão; nesse caso substitua-o.

## Fluxo recomendado

1. **Começar projeto:** crie um projeto ou use Abrir pela pasta. Escolha as pastas
   onde os vídeos e o B-roll já existem. Não copie seu acervo para cada projeto.
2. **Criar narração:** opcional se você já tem áudio. Abra o VoiceStudio, carregue
   as vozes, cole o roteiro e ouça uma amostra. Gerar e preparar narração gera o
   original, ajusta pausas e transcreve o áudio final. Tudo fica em 03_Audio.
3. **Analisar roteiro:** escolha Groq para compreensão por IA, ou Local para regras
   simples. Confira o contexto. Groq usa sua chave, o texto e descrições do material;
   seus arquivos de vídeo e áudio não são enviados a ele.
4. **Abrir recorte no CMD:** abre uma janela separada, independente do navegador.
   Espere aparecer FINALIZADO nessa janela. Depois clique **Atualizar cenas**.
5. **Buscar material:** baixe imagens e B-roll, confira as fotos na galeria e marque
   Usar esta imagem. Salve a escolha. Imagens IA já existentes podem ser importadas.
6. **Gerar vídeo:** abra Revisar vídeo, assista/troque cenas, confira textos e confirme
   os trechos. Envie para um projeto NOVO e VAZIO no Drift com acesso de agente ativo.

## Como o recorte funciona agora

O MontaVideo escreve RECORTAR_MONTAVIDEO.bat na área 04_Cortes e em cada pasta que
contém vídeos pendentes. O botão executa o BAT principal em um CMD visível.
Ele prefere o comando scenedetect que já está instalado no PATH do seu Windows,
como no BAT fornecido pelo usuário. Se não estiver disponível, usa a instalação
embutida. O comando é detect-content split-video. Não captura nem esconde o
progresso do detector. O navegador não acompanha porcentagens nem controla esse CMD.
Você pode continuar navegando ou fechar o MontaVideo enquanto o CMD trabalha.

Saída de cada fonte: ao lado do original, dentro de
Cenas_Separadas_MontaVideo / nome-do-video_identificador.
O arquivo concluido.json só é escrito depois que o detector termina com sucesso.
Atualizar cenas encontra essas pastas automaticamente, sem pedir novos caminhos.
Não usa vídeos longos pendentes como se já estivessem cortados. Reutiliza recortes
concluídos, inclusive os manifestos compatíveis da versão 0.6 em 04_Cortes.

Se suas fontes JÁ são cenas recortadas, marque a opção de projeto/B-roll e clique
Atualizar cenas, sem executar novamente o detector. Para aproveitar cortes feitos
por outro BAT, selecione a pasta desses cortes uma vez como fonte e marque a opção.

A primeira execução ainda precisa ler os frames e produzir arquivos. Um BAT não
elimina esse trabalho. Se o seu detector também travar no CMD, a saída ficará visível
para diagnóstico; feche o CMD para interromper. Uma interrupção forçada pode deixar
executando.lock na pasta daquela fonte. Confirme que nenhum recorte está rodando
antes de remover somente esse arquivo e tentar novamente. Os originais não são apagados.

## VoiceStudio e áudio

VoiceStudio é uma instalação separada: https://github.com/debpalash/VoiceStudio/releases
Abra-o, baixe um modelo adequado e configure a voz. Use o endereço local do backend,
normalmente http://127.0.0.1:3900. A integração usa /health, /profiles e /generate.
O pacote não inclui os modelos de voz nem instala o VoiceStudio silenciosamente.

A geração é dividida por frases em partes reaproveitáveis. Se interromper, as partes
já concluídas ficam em 03_Audio/partes. O cancelamento para o pedido do MontaVideo;
uma geração já recebida pelo VoiceStudio pode continuar nele.

O original é preservado. O ajuste de pausas cria um WAV final e um mapa dos cortes.
A pausa padrão é 0,12 s e somente silêncios de pelo menos 0,25 s são considerados.
A sensibilidade padrão é -45 dB. Ouça o resultado; não elimina respirações com a
precisão de um editor humano. Também existe Só sincronizar para manter as pausas.

Whisper transcreve o áudio FINAL, gera SRT e JSON com tempos de palavras. Esses
tempos são estimativas do reconhecimento de fala e precisam de revisão em nomes
próprios. Não inventa uma duração por palavra a partir do tamanho do roteiro.
Se CUDA falhar, tenta CPU. O primeiro uso baixa o modelo de transcrição.

## Busca de material

- Pexels e Pixabay: cadastre suas próprias chaves em Suas conexões. As buscas seguem
  os limites de sua conta. B-roll vai para 08_Broll_Baixado; fotos para 05_Imagens.
- Google pelo Chrome: exige Chrome instalado. Selenium abre um navegador separado
  e tenta obter imagens originais em boa resolução. O perfil de busca é separado
  do seu perfil pessoal. Consentimento ou bloqueios podem exigir sua intervenção;
  não contorna CAPTCHA e não há garantia de resultados para toda consulta.
- Google por Serper: integração opcional com sua chave desse serviço; créditos e
  custos dependem da conta. Não é uma chave oficial do Google.
- Wikimedia Commons: alternativa explícita, sem substituir escondido outra fonte.

Cada download tem registro .fonte.json com origem, consulta e autoria quando
fornecida. Confira se uma imagem mostra realmente o projeto mencionado e sua licença.
Fotos pequenas e duplicatas são filtradas. Não são gerados cartões/PNG de texto
para disfarçar uma falha de busca. Nenhuma chave de terceiros está incluída.

## Planejamento e edição

Groq analisa o roteiro e, na atualização de cenas, compara nomes de arquivos com o
contexto. O modo Local usa regras e palavras-chave: não possui um modelo de linguagem.
Nenhum dos modos nesta versão reconhece visualmente cada pessoa, país ou modelo de
veículo dentro dos frames. Nome genérico como cidade.mp4 não prova a localização.
Um erro Groq mostra o detalhe recebido e não troca silenciosamente para Local.
HTTP 403 depende da autorização do provedor; o software não pode garantir sua liberação.

A montagem começa com vídeo, varia as durações, alterna fontes com prioridades
ponderadas e equilibra os vídeos originais. Não segue o antigo ciclo fixo de nove
takes. A IA pode sugerir tipo de visual e textos curtos extraídos da fala. Os textos
podem ser corrigidos na revisão e chegam ao Drift como texto editável em negrito,
com entrada e saída animadas. Os tempos por palavra ajudam quando estão disponíveis.

Fotos fora de 16:9 recebem BG em uma composição 1920x1080. Foto e fundo fazem o
mesmo zoom; os originais são preservados. A composição de BG é uma imagem única,
não duas camadas independentes. Não há parallax multicamada automático nesta versão.
Há zoom in/out e dissoluções entre clipes compatíveis; trocas entre tipos usam corte.
A prévia local mostra o material, sem todos os efeitos finais; confira-os no Drift.
A geração de imagens por IA continua sendo uma integração futura, com importação
local já disponível. Arquivos insuficientes podem deixar trechos pendentes para revisão.

## O que foi validado

Ver VALIDACAO.md. Os testes foram feitos em Linux. Não foi possível executar aqui
seu Windows, sua RTX, o VoiceStudio real com seus modelos, suas APIs autenticadas
ou o Drift desktop. O pacote não é anunciado como “zero bugs” ou funcionamento
confirmado nessa máquina sem esse teste final.
