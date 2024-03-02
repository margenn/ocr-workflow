## PÚBLICO

Desenvolvedores que possuam conhecimentos em Python que tenham interesse em ter um processo completo de OCR para estudo / utilização.

Este processo foi desenvolvido e testado somente em Linux. Para windows, será necessário o desenvolvimento de uma função para detecção do tamanho do monitor.


## INTRODUÇÃO

O script `ocr-workflow.py` contém os passos necessários para realizar a extração do texto contido em diversos documentos digitalizados por fotografias. O processo lê todas as imagens seguindo a ordem alfabética dos arquivos e exporta o resultado das extrações para um único arquivo texto.

Para executar, siga estes passos:

1. Coloque as fotos em uma pasta qualquer
2. Configure os parâmetros de execução
3. Execute o script ocr-workflow.py

Qualidade das fotos:

- Use a resolução máxima da câmera (48MP preferencialmente)
- A folha deve ter os 4 cantos dentro da foto e precisa estar minimamente alinhada com a orientação da camera.
- O papel deve estar sobre um fundo escuro

Os processo é dividido em 3 blocos principais:

1. TRATAMENTO_IMAGENS: As imagens da `PASTA_ENTRADA` recebem um tratamento prévio com o [OpenCV](https://opencv.org/)
2. EXTRACAO_TEXTO: O texto é extraído das imagens tratadas com o [Tesseract](https://github.com/tesseract-ocr/tesseract)
3. CORRECAO_TEXTO: O texto resultante passa por correções seguindo uma sequência de regras pré estabelecidas.


## EXECUTANDO PELA PRIMEIRA VEZ

Configure os parâmetros de ocr-workflow.py:418 como apresentado abaixo:

```python
PASTA_ENTRADA = '/pasta/onde/estao/suas/imagens'
LOG_LEVEL = 0
TRATAMENTO_IMAGENS = 1
LIMITE_IMAGENS = 1
EXTRACAO_TEXTO = 1
CORRECAO_TEXTO = 1
```

Execute o script.

Vocẽ deverá ver uma nova pasta `PASTA_ENTRADA/saida'` com as imagens tratadas e o texto extraído. Não se preocupe com o resultado, os ajustes serão feitos adiante.


## EXECUTANDO EM MODO DEBUG

Altere estes parâmetros como mostrado:

```python
LOG_LEVEL = 1
EXTRACAO_TEXTO = 0
CORRECAO_TEXTO = 0
```

Execute o script. Irão aparecer as imagens intermediárias do processo.

Vértices encontrados:


![alt](/img/vert-identified.jpg)


Os pontos <span style='color:#f0f'>ROSA</span>, representam o contorno da folha. Os 4 pontos em <span style='color:#0f0'>VERDE</span>, os vértices identificados.

Clique na imagem e pressione qualquer tecla para apresentar a próxima (aqui está sendo mostrada parcialmente devido o tamanho da mesma)


![alt](/img/marcacoes.png)


Os pontos considerados ruído, estão marcados com um <span style='color:#f00'>CÍRCULO VERMELHO</span> junto com o seu raio e ID.

Os pontos ligados a um caractere, estão identificados por uma <span style='color:#0f0'> LINHA VERDE</span>.

Os caracteres identificados na varredura estão identificados por um <span style='color:#44f'>RETÂNGULO AZUL</span> junto com tamanho do seu raio.

Clique na imagem e depois em qualquer tecla para fechar a janela e continuar o processamento. A pasta de saída agora contém a imagem de debug em alta resolução para conferência dos ruídos identificados.


## CALIBRANDO OS PARÂMETROS

Isto é feito através da execução sucessiva de ajuste dos parâmetros e execução do script em modo debug até que os vértices e ruídos tenham sido corretamente identificados.

Seguem os parâmetros e valores sugeridos para fotos em 48MP. Os valores podem mudar dependendo do tamanho do caractere e a distância da câmera.

```python
REMOVER_BORDAS = [0.5, 0.5, 0.5, 0.5]       # Percentual de remoção das 4 bordas
BINARIZACAO_BLUR = 3                        # Suavização inicial da imagem em pixels.
BINARIZACAO_BLOCKSIZE = 101                 # Bloco de limitar adaptativo.
BINARIZACAO_LIMIAR = 20                     # Limiar para analise de limiar adaptativo.
NOISE_VERYSMALL = 2                         # Objetos de até este raio são removidos
NOISE_SMALL = 5                             # Objetos ISOLADOS com até este raio são removidos
NOISE_ISOLATION_MIN = 40                    # Distância mínima para considerar isolamento
CHAR_RADIUS_MIN = 4                         # Raio mínimo de um caractere (Ex: pingo do i)
```


Depois dos ajustes feitos, coloque em modo de produção e modifique estes parâmetros para converter algumas imagens da pasta:

```python
LOG_LEVEL = 0
LIMITE_IMAGENS = 10 # ou qualquer outro limite que deseje
```

Depois de exportar as imagens, execute somente os blocos de extração e correção de texto

```python
LOG_LEVEL = 0
TRATAMENTO_IMAGENS = 0
EXTRACAO_TEXTO = 1
CORRECAO_TEXTO = 1
```

Depois de executar o script, desligue o bloco de extração de textos. :

```python
EXTRACAO_TEXTO = 0
```

Analise `PASTA_SAIDA/TEXTO_EXTRAIDO_CORRIGIDO.txt'` e modifique o parametro `SUBSTITUICOES` com a lista dos 'patterns' e 'replaces' necessários. (Se vocẽ ainda não conhece regex, eis um bom motivo pra aprender)

Execute o script novamente e confira os resultados. Repita este ciclo até que as correções estejam implementadas.


SEU PROCESSO ESTÁ CALIBRADO.

Habilite todos os blocos e aumente o valor do limitador de imagens.

```python
LOG_LEVEL = 0
TRATAMENTO_IMAGENS = 1
EXTRACAO_TEXTO = 1
CORRECAO_TEXTO = 1
LIMITE_IMAGENS = 999999
```

SEU PROCESSO AGORA ESTÁ PRONTO PARA RECEBER E PROCESSAR NOVAS PASTAS.


## ENTENDENDO O FUNCIONAMENTO DO SCRIPT

O problema da digitalização por fotografia em relação ao um scanner convencional, é que a imagem apresenta distorções como curvatura das bordas, deformação trapezoidal e variações de luminosidade:

![alt](/img/issues.jpg)


É necessário fazer um tratamento prévio em cada imagem antes de submetê-las a extração de texto por OCR. Este tratamento passa pelos seguintes passos:

- Identificação dos 4 vértices da folha
- Correção das deformações trapezoidais
- Eliminação de bordas escuras causadas pela curvatura das bordas da folha
- Conversão da imagem em preto e branco (binarização)
- Remoção de ruídos. Eles podem ser interpretados como '.' pela etapa de OCR
- Gravação da imagem corrigida


### Identificação dos 4 vértices da folha

Algumas abordagens adotam esta sequência: identificação dos contornos, identificação das maiores retas e cálculo dos pontos de intersecção.

Essa abordagem não funciona para fotos. O motivo é uma sutil curvatura das bordas. Esta curvatura é quase imperceptível, porém inviabiliza este tipo de solução.

A sequência que funcionou foi esta: Identificar todos os pontos do maior contorno (folha) e selecionar os 4 mais próximos dos 4 vértices da imagem.

![alt](/img/vertices.jpg)


### Homogenização das dimensões

Uma vez que os vértices foram identificados, são calculados os vértices do menor retângulo que os contém. Em seguida, a imagem é retificada para se adequar ao novo formato, corrigindo assim a distorção trapezoidal.

Pense em uma imagem desenhada em uma folha de borracha, onde vocẽ 'estica' as bordas até fazer ela caber em um retângulo perfeito.

```python
.....
matrix = cv.getPerspectiveTransform(origem_np, destino_np)
image_aligned = cv.warpPerspective(image, matrix, (largura, altura))
.....
```


### Eliminação das bordas

A imagem retificada ficará com alguma 'sujeira' nas bordas, resultante da curvatura das mesmas na foto original.

Então é necessário remover alguns pixels de cada um dos 4 lados. Isso é feito definindo os percentuais de cada lado. A matriz inicia a partir da borda superior em sentindo horário. Os percentuais devem ser ajustados de acordo com a necessidade.

```python
.....
image_crop = crop_bordas(image_aligned, REMOVER_BORDAS)
.....
```


### Binarização da imagem

Após a retificação da página e remoção das bordas, a imagem precisa ser convertida para preto-e-branco (binarização).

O desafio aqui é lidar com as variações de luminosidade ao longo da imagem.

Para resolver esse problema, o OpenCV possui um recurso chamado 'threshold adaptativo'. Ele divide a imagem em quadrantes, cujo tamanho é definido pela propriedade blocksize, em seguida calcula o melhor limiar parcial para cada um deles. Ele toma por base um limiar genérico que é fornecido na chamada da função:

```python
image_bw = cv.adaptiveThreshold(blurred, 255, cv.ADAPTIVE_THRESH_MEAN_C, cv.THRESH_BINARY, blocksize, limiar)
```


### Remoção de ruídos

Primeiro são obtidos todos os contornos da imagem. Contorno, é tudo que o OpenCV identifica como um grupo de pontos pretos. Um único pixel isolado é identificado como um contorno.

```python
contours, hierarchy = cv.findContours(image_bw, cv.RETR_TREE, cv.CHAIN_APPROX_SIMPLE)
```

O cv.RETR_TREE obtem uma estrutura hierarquizada. Essa hierarquia é fundamental para identificar os contornos hierarquizados. Aqui, são os 'buracos' dentro de cada letra.

O cv.CHAIN_APPROX_SIMPLE obtém uma versão simplificada dos contornos.

A identificação dos ruídos obedece a 3 regras:

1. Não pode ser um 'buraco' (Ex: O pequeno triângulo contido dentro da letra "A")
2. Deve ser um contorno com até `NOISE_VERYSMALL` pixels de raio, ou...
3. Deve ser um contorno ISOLADO com até `NOISE_SMALL` pixels de raio e seu centro deve estar afastado a pelo menos `NOISE_DIST_MIN` pixels do centro do caractere mais próximo.


## CONCLUSÕES

A parte mais 'desafiadora' desse desenvolvimento, foi encontrar o melhor algoritmo para detectar os cantos da folha. A partir da identificação destes 4 vértices, a retificação/extração da página é feita pelo OpenCV com apenas duas linhas de código, como mostrado.

Outro problema foi lidar com as variações de luminosidade ao longo da foto. O limiar que funcionava para o meio da imagem, não funcionava para os cantos e vice-versa. Novamente, o OpenCV vem como uma solução já pronta que é o adaptiveThreshold. Maiores informações [aqui](https://stackabuse.com/opencv-adaptive-thresholding-in-python-with-cv2adaptivethreshold/)

Na etapa de redução de ruídos, o que geralmente fazem, é criar uma nova imagem em branco e apenas transferir contornos com tamanho maior que N pixels. Essa abordagem não funcionou porque as letras perdiam os 'buracos' (traduzido como está na documentação). Aqui, a abordagem foi um pouco diferente. Os contornos identificados como ruído foram 'tampados' por um círculo branco, o que na prática, obtém o mesmo resultado. (Quem lembra do liquidpaper?)

Este trabalho foi resultado de alguns tutoriais, ChatGPT, StackOverflow, Documentação do OpenCV, Documentação do Tesseract e desenvolvimento próprio.

Este projeto foi desenvolvido no VS Code rodando no Xubuntu com plugins Python, Python Debugger e Regex Previewer.
