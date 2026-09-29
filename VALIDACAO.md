# Validação 0.7.1
58 testes passaram. Novo contrato de voz testado com serviço simulado, perfil fixo em múltiplos blocos, rejeição de perfil sem referência, materialização de arquétipo e galeria na interface (DOM). VoiceStudio neural e Windows reais ainda não validados.

# Validação da versão 0.7

Ambiente de teste: Linux, Python 3.12. O pacote Windows prepara Python 3.11.9.

## Executado

- 54 testes automatizados passaram: seleção temporal, limites dos cortes, equilíbrio
  entre fontes, abertura obrigatória com vídeo, persistência de configurações,
  transporte HTTP, tratamento de cancelamento, imagens/BG e pistas compatíveis.
- Recorte real por processo independente: vídeo sintético de duas cenas, nome com
  espaços, exclamação e percentual. PySceneDetect criou dois MP4. Atualizar cenas
  encontrou ambos, identificou o original e excluiu o vídeo longo do catálogo de takes.
  A segunda execução reaproveitou os arquivos sem recodificá-los.
- FFmpeg real: áudio de 3 s com 1 s de silêncio virou aproximadamente 2,12 s,
  preservando o original e registrando o mapa dos intervalos.
- VoiceStudio simulado em servidor HTTP local: leitura de vozes, pedido de síntese,
  recebimento de WAV, processamento real do arquivo e cache de partes.
- Sincronização: SRT/JSON mantêm vínculo com o áudio final por impressão do arquivo;
  a transcrição foi simulada no teste da integração, não sua precisão linguística.
- HTTP real do MontaVideo: criação, salvamento de conexões sem perder caminhos,
  contexto, catalogação, plano completo, MP4 de prévia, salvamento e reabertura pela pasta.
- Interface em jsdom: navegação, parsing do guia Drift, carregamento de projeto,
  galeria e revisão. JavaScript passou na verificação de sintaxe.
- Pexels, Pixabay e Serper: respostas simuladas com formatos das APIs, seleção de HD,
  escolha do original em vez da miniatura, autoria e cache.

## Não executado neste ambiente

- Janela CMD, seletor COM, DPAPI e desktop/WebView2 no Windows real.
- VoiceStudio real e geração com o modelo de voz do usuário na RTX 4060.
- Chamadas autenticadas com as chaves pessoais Groq, Pexels, Pixabay e Serper.
- Download Google no Chrome do usuário, sujeito a páginas de consentimento/bloqueio.
- Renderização e exportação final no Drift desktop real. O cliente segue o código
  consultado do Drift v0.6.0; montagem básica/pistas foram verificadas com simulações.
- Desempenho com todo o acervo pessoal, vídeos longos ou dezenas de milhares de cortes.

Os testes não eliminam a necessidade de conferir voz, cenas, identidade das fotos,
textos e exportação no ambiente do usuário. Não há promessa de alinhamento perfeito
por palavra, reconhecimento visual ou ausência de bloqueios externos.
