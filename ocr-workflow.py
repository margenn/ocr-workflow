import cv2 as cv, numpy as np, os, pytesseract, re, subprocess
from PIL import Image


def calcular_vertices(image, limiar, log_level=0):
	'''
	Procura por um quadrilátero de cor clara sobre um fundo escuro (pagina escaneada)
	Cada vertice deste quadrilatero precisa estar em um quadrante da foto
	Aqui a abordagem é diferente de outros métodos:
	Depois de achar os pontos referentes ao contorno da página escaneada,
	seleciona-se os que estiverem mais próximos aos 4 vértices da imagem
	Essa abordagem funciona muito bem para páginas fotografadas, onde os cantos
	da folha não são perfeitamente retos

	Args:
		image: Array NumPy contendo a imagem (imagem original colorida)
		limiar: Abaixo desse valor, o pixel da imagem sera convertido para 0 na binarização

	Returns:
		Array: Coordenadas dos 4 vértices. Canto Sup Esq. Sentido Horário.
		NumPy Array: Imagem com as marcações plotadas para conferência
	'''

	# Define as cores das marcaçoes
	GREEN=(0,255,0); PURPLE=(255,0,255)

	# Dimensões da imagem
	height, width = image.shape[:2]
	print(f"Dimensões da imagem: {height} x {width}" )

	# Converte a imagem para tons de cinza
	imageGray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)

	# Binariza a imagem
	print(f"Convertendo imagem para preto e branco com limiar = {limiar}")
	_, image_bw = cv.threshold(imageGray, limiar, 255, cv.THRESH_BINARY)

	# Copia a imagem binarizada para uma imagem colorida. (As marcacoes posteriores serão coloridas).
	image_debug = cv.cvtColor(image_bw, cv.COLOR_GRAY2BGR)

	# Encontra os contornos externos
	contours, _ = cv.findContours(image_bw, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)

	# Encontra o maior contorno (pagina escaneada)
	largest_contour = max(contours, key=cv.contourArea)

	# Plota o contorno na imagem de conferência
	cv.drawContours(image_debug, largest_contour, -1, PURPLE, round(0.005 * width))

	# Encontra os vértices da imagem de origem
	image_corners = [(0, 0), (width - 1, 0), (width - 1, height - 1), (0, height - 1)]

	# Calcula a distância dos vértices do quadrilátero até as quatro extremidades da imagem
	all_distances = []; closest_points = []
	for vertex in largest_contour:
		x, y = vertex[0]
		distances = [np.sqrt((x - corner[0]) ** 2 + (y - corner[1]) ** 2) for corner in image_corners]
		closest_corner_index = np.argmin(distances)
		all_distances.append((x, y, closest_corner_index, distances[closest_corner_index]))

	# Transforma a array com as distancias de cada vertice em uma array NumPy
	closest_points_np = np.array(all_distances)
	# Ordena pelas terceira e quarta colunas. (closest_corner_index, distances[closest_corner_index])
	sorted_indices = np.lexsort((closest_points_np[:, 3], closest_points_np[:, 2]))
	closest_points_np = closest_points_np[sorted_indices]
	# Obtem apenas o primeiro elemento de cada terceira coluna, menor distancia de cada closest_corner_index
	unique_idxs = np.unique(closest_points_np[:, 2], return_index=True)[1]
	# Transforma a array NumPy em uma array comum
	closest_points = closest_points_np[unique_idxs].tolist()

	# Transforma as coordenadas encontradas em numeros inteiros
	vertices = list(map(lambda item: (round(item[0]), round(item[1])), closest_points))

	if LOG_LEVEL >= 1: print(f"Vertices detectados: {vertices}")

	# plota os vertices encontrados na imagem de debug
	if LOG_LEVEL >= 1:
		for point in vertices:
			image_debug = cv.circle(image_debug, (round(point[0]), round(point[1])), round(0.01 * width), GREEN, -1)

	return vertices, image_debug


def convert_bw(image_gs, blursize=3, blocksize=101, limiar=20, noise_verysmall=2, \
		noise_small=4, noise_dist_min=50, char_radius_min=5):
	'''
	Converte imagem GRAYSCALE para BINARY usando vários recursos de otimização,
	como Threshold adaptativo e redução de ruídos

	Args:
		image_gs: Imagem em grayscale
		blursize: Intensidade do desfoque inicial da imagem.
		blocksize: Tamanho do bloco de analise do adaptiveThreshold.
		limiar: Limite de brilho max para converter pixel para preto.
		noise_verysmall: Contornos com raio até aqui são imediatamente descartados.
		noise_small: Contornos isolados com até este raio sao descartados.
		noise_dist_min: Distância mínima do centro de outros caracteres para um ruido ser considerado isolado.
		char_radius_min: Raio mínimo para que um contorno seja considerado um caractere.
	Returns:
		NumPy Array: Imagem binária
	'''
	# encontra a maior raio possivel de um contorno valido
	contour_maxsize = min(image_gs.shape[:2]) / 4

	# Aplica um blur na imagem para suavizar o fundo
	blurred = cv.GaussianBlur(image_gs, (blursize, blursize), 0)

	# Binariza a imagem
	image_bw = cv.adaptiveThreshold(blurred, 255, cv.ADAPTIVE_THRESH_MEAN_C, cv.THRESH_BINARY, blocksize, limiar)
	print(f'Binarizando imagem: Blur={blursize} BlockSize={blocksize} Limiar={limiar}')

	# Coloriza a imagem para receber as marcações
	if LOG_LEVEL > 0: image_debug = cv.cvtColor(image_bw, cv.COLOR_GRAY2BGR)

	# Levanta os contornos externos da imagem
	contours, hierarchy = cv.findContours(image_bw, cv.RETR_TREE, cv.CHAIN_APPROX_SIMPLE)

	# Carrega arrays com contornos, quadrados e circulos contidos em cada contorno encontrado na imagem
	# Ref: https://docs.opencv.org/3.4/da/d0c/tutorial_bounding_rects_circles.html
	contours_poly = [None]*len(contours); bound_rect = [None]*len(contours)
	centers = [None]*len(contours); radius = [None]*len(contours)
	for i, contourn in enumerate(contours):
		contours_poly[i] = cv.approxPolyDP(contourn, 3, True)
		bound_rect[i] = cv.boundingRect(contours_poly[i])
		circle_item = cv.minEnclosingCircle(contours_poly[i])
		centers[i] = (round(circle_item[0][0]), round(circle_item[0][1]))
		radius[i] =  round(circle_item[1])

	# Identifica e apaga todos os contornos considerados ruido
	WHITE=255; RED=(0,0,255); GREEN=(0,255,0); BLUE=(255,0,0); MARKRADIUS=30
	for i in range(len(contours)):
		# define se o contorno é um rúido
		noise, reason = is_noise(i, centers, radius, hierarchy, noise_verysmall, noise_small, noise_dist_min, char_radius_min, (noise_dist_min*2))
		if noise:
			if LOG_LEVEL == 0:
				# 'Tapa' os ruidos sobreponto um circulo branco com raio 2 pixels maior que o do ruído
				cv.circle(image_bw, (centers[i][0], centers[i][1]), radius[i]+2 , WHITE, -1)
			else:
				# Caso esteja em modo debug, plota as marcações necessárias para analisar o comportamento da remoção de ruídos
				# print(f"i:{i} Coord:{centers[i]} Radius:{radius[i]} Hierarchy:{hierarchy[0][i]}    ")
				cv.circle(image_debug, (centers[i][0], centers[i][1]), MARKRADIUS, RED, 1) # marca o ruido detectado (debug)
				imprimir_texto(image_debug, ('r:'+str(radius[i])+' '+'i:'+str(i)), (centers[i][0], centers[i][1]), RED)
		else:
			if LOG_LEVEL > 0:
				# Caso esteja em modo debug, plota os contornos que NÃO foram considerados ruído
				#cv.drawContours(image_debug, contours_poly, i, BLUE)
				cantosupesq = (int(bound_rect[i][0]), int(bound_rect[i][1]))
				cantoinfdir = (int(bound_rect[i][0]+bound_rect[i][2]), int(bound_rect[i][1]+bound_rect[i][3]))
				posicaotexto = (int(bound_rect[i][0]), int(bound_rect[i][1])-2)
				cv.rectangle(image_debug, cantosupesq, cantoinfdir, BLUE, 1)
				imprimir_texto(image_debug, ('r:'+str(radius[i])), posicaotexto, BLUE)
				if reason[0] == 'close':
					cv.line(image_debug, (centers[i][0], centers[i][1]), (centers[reason[1]][0], centers[reason[1]][1]), GREEN, 2)
				#cv.circle(image_debug, (centers[i][0], centers[i][1]), MARKRADIUS			, GREEN,  1)

	if LOG_LEVEL == 0:
		return image_bw
	else:
		return image_debug


def corrige_texto(texto, replacements):
	"""
	Pós processamento do texto extraído
	Efetua correções dos erros mais comuns

	A array replaces pode ter:
		[regex, string] para substituicoes simples
		[regex, regex] para substituicao usando back reference
		[regex, lambda] para substituicao por funcoes que usam o backreference como parametro

	Declarando flags dentro do proprio regex
		(?i) Case Insensitive
		(?m) Multiline. Permite que ^ e $ correspondam ao início e ao fim de cada linha
		(?s): Faz com que o ponto (.) corresponda a qualquer caractere, incluindo novas linhas.
		sintaxe para 2 flags: r'(?i)(?m)restantedaregex'

	Args:
		texto: String com o texto extraído das imagens
		replacements: lista de tuples com os patterns (regex) e seus replacements

	Returns:
		String: texto com as substituições aplicadas
	"""

	texto_corrigido = texto

	for pattern, replacement in replacements.items():
		texto_corrigido = re.sub(pattern, replacement, texto_corrigido)

	return texto_corrigido


def criar_pasta(path):
	'''
	Cria uma pasta, caso ela ainda não exista.

	Args:
		path: Caminho completo da pasta
	'''

	if not os.path.exists(path):
		os.makedirs(path)
		print(f'A pasta {path} foi criada com sucesso.')
	else:
		print(f'A pasta {path} já existe.')
	return None


def crop_bordas(image, percentuais):
	'''
	Remove as bordas de uma imagem

	Args:
		image: Array NumPy contendo a imagem
		percentuais: Array com 4 percentuais representando o quanto deve ser removido de cada lado
			iniciando pelo canto superior, sentido horário
	Returns:
		Array NumPy: Imagem com as bordas removidas
	'''

	altura, largura = image.shape

	corte_superior = int(altura * (percentuais[0]/100))
	corte_direita = int(largura * (percentuais[1]/100))
	corte_inferior = int(altura * (percentuais[2]/100))
	corte_esquerda = int(largura * (percentuais[3]/100))

	return image[corte_superior:-corte_inferior, corte_esquerda:-corte_direita]


def get_screen_resolution_linux():
	'''
	Retorna a resolução do monitor

	Returns:
		Int: Largura
		Int: Altura
	'''
	output = subprocess.check_output(['xrandr']).decode('utf-8')
	for line in output.splitlines():
		if ' current' in line:
			dim = re.findall(r'current (\d+) x (\d+)', line)
			largura = 1920; altura=1080
			if (dim):
				largura = dim[0][0];altura = dim[0][1]
			break
	return int(largura), int(altura)


def image_align(image, vertices):
	'''
	Extrai e alinha o quadrilátero contido na imagem
	image: Imagem contendo um quadrilatero
	vertices: Array contendo as coordenadas dos 4 vértices do quadrilatero
	'''
	# determina as coordenadas do retangulo que contem o quadrilatero
	min_x = min(p[0] for p in vertices)
	min_y = min(p[1] for p in vertices)
	max_x = max(p[0] for p in vertices)
	max_y = max(p[1] for p in vertices)
	# Converte os vertices em uma array numpy
	origem_np = np.array([[float(vertice[0]), float(vertice[1])] for vertice in vertices], dtype=np.float32)
	# Define as dimensões do retangulo destino
	largura, altura = max_x - min_x, max_y - min_y
	print(f"image_align. Dimensões do retangulo que conterá o quadrilatero extraído da imagem original: {largura} x {altura}")
	destino_np = np.array([[0, 0], [largura - 1, 0], [largura - 1, altura - 1], [0, altura - 1]], dtype=np.float32)
	# Calcular a matriz de transformação de perspectiva
	matrix = cv.getPerspectiveTransform(origem_np, destino_np)
	# Extrai e alinha o quadrilatero, aplicando uma transformação de perspectiva
	image_aligned = cv.warpPerspective(image, matrix, (largura, altura))
	return image_aligned


def imprimir_texto(image, texto, coordenadas, cor):
	"""
	Imprime um texto em uma imagem nas coordenadas especificadas.

	Args:
		image (numpy.ndarray): A imagem onde o texto será desenhado.
		texto (str): O texto a ser impresso na imagem.
		coordenadas (tuple): Um par de coordenadas (x, y) onde o texto será desenhado.
	"""
	fonte = cv.FONT_HERSHEY_SIMPLEX
	tamanho_fonte = 0.5
	espessura = 1

	cv.putText(image, texto, coordenadas, fonte, tamanho_fonte, cor, espessura)


def is_noise(i, centers, radius, hierarchy, noise_verysmall, noise_small, noise_dist_min, char_radius_min, char_radius_max):
	'''
	Determina se um contorno é um ruído

	Args:
		i: index do contorno atual
		centers: array contendo os centros de cada contorno
		radius: array contendo os raios de cada contorno
		hierarchy: array contendo as informacoes de hierarquia
		noise_verysmall: Raio maximo para ser considerado ruido
		noise_small: Raio maximo de um contorno isolado
		noise_dist_min: Isolamente mínimo X e Y de outros objetos
		char_radius_min: Raio minimo de um caractere (Ex. Ponto)
		char_radius_max: Raio maximo de um caractere (Ex. Fonte de títulos)

	Returns:
		Bool: True quando o contorno for considerado ruído
		Reason: Array com informações adicionais
			0: Motivo
			1: ID do contorno associado
	'''
	# Buracos são desconsiderados, pois precisam ser mantidos. Ex: triangulo dentro da letra "A"
	parent_contour = hierarchy[0][i][3]
	if parent_contour > 0 and radius[parent_contour] < char_radius_max:
		return False, ['hole', parent_contour]

	# Contornos muito pequenos são imediatamente considerados ruído
	if radius[i] <= noise_verysmall:
		return True, ['verysmall', -1]

	# Contornos pequenos precisam estar longe de qualquer outro contorno grande para serem considerados ruído
	if radius[i] <= noise_small:
		# Verifica a proximidade com algum contorno grande
		# Essa validação serve, por ex, para que o ponto da letra "i" não seja interpretado como ruído
		for ii, c in enumerate(centers):
			if i != ii and (abs(c[0] - centers[i][0]) <= noise_dist_min) \
					and (abs(c[1] - centers[i][1]) <= noise_dist_min) and radius[ii] >= char_radius_min:
				return False, ['close', ii]
		return True, ['far', -1]

	return False, ['default', -1]


def list_files_from_folder(folder, regex):
	"""
	Retorna uma lista de todos as imagens de uma determinada pasta em ordem alfabetica

	Args:
		folder: String com o caminho da pasta
		regex: Expressão regular contendo o que deve ser filtrado

	Returns:
		array: Lista dos caminhos completos dos arquivos
	"""
	regexp = re.compile(regex, re.IGNORECASE)

	files = []
	for file in os.listdir(folder):
		fullpath = os.path.join(folder, file)
		if (os.path.isfile(fullpath) and regexp.search(str(fullpath))):
			files.append(str(fullpath))

	return sorted(files)


def resize_to_screen(image):
	"""
	Redimensiona uma imagem para que ele caiba na tela

	Args:
		image: Array NumPy contendo a imagem
		escala: 1.0 pega a

	Returns:
		array: Lista dos caminhos completos dos arquivos
	"""
	# Manter 10% de área livre na tela
	ESPACO_LIVRE = 0.1

	# Define o resolução do monitor
	largura_tela, altura_tela = get_screen_resolution_linux()
	altura_imagem, largura_imagem = image.shape[:2]

	# Calcular a proporção de redimensionamento da imagem
	proporcao_largura = largura_tela * (1.0 - ESPACO_LIVRE) / largura_imagem
	proporcao_altura = altura_tela * (1.0 - ESPACO_LIVRE) / altura_imagem
	proporcao = min(proporcao_largura, proporcao_altura)

	# Redimensiona a imagem, mantendo as proporções originais
	nova_largura = int(largura_imagem * proporcao)
	nova_altura = int(altura_imagem * proporcao)

	if largura_imagem > largura_tela or altura_imagem > altura_tela:
		imagem_redimensionada = cv.resize(image, (nova_largura, nova_altura))
		return imagem_redimensionada
	else:
		return image


def show_image(image):
	"""
	Abre uma janela com a imagem e aguarda qualquer tecla para fecha-la

	Args:
		image: Array NumPy contendo a imagem
		escala: 1.0 pega a

	Returns:
		array: Lista dos caminhos completos dos arquivos
	"""
	update_image(image)
	cv.destroyAllWindows()
	return None


def update_image(image):
	'''
	Abre uma janela para apresentar a imagem, mas nao a destroy depois de tecla pressionada
	Caso a janela já esteja aberta, atualiza seu conteudo
	'''
	cv.imshow('Image', image)
	cv.waitKey(0)
	return None


########################################################################################################################

if __name__ == "__main__":

	# INICIO DAS CONFIGURAÇÕES
	####################################################################################################################

	PASTA_ENTRADA =                             '/home/ma/Documents/githubProjetos/ocr-workflow/sample'
	LOG_LEVEL = 0                               # 0:Modo PROD, 1:Modo DEV (Ajustes dos parãmetros abaixo)
	TRATAMENTO_IMAGENS = 1                      # Tratar imagens?
	LIMITE_IMAGENS = 1                          # Somente as N primerias imagens da pasta serão processadas
	EXTRACAO_TEXTO = 1                          # Extrair texto?
	CORRECAO_TEXTO = 1                          # Corrigir texto?

	# AJUSTES PARA A PRIMEIRA ETAPA (DETECÇÃO DOS 4 VÉRTICES DA FOLHA)
	LIMIAR_BINARIZACAO_DETECCAO_BORDAS = 120    # Limiar de binarizacao inicial, ajustar até que todo o entorno da folha fique preto

	# AJUSTES PARA A SEGUNDA ETAPA (ALINHAMENTO, BINARIZAÇÃO E LIMPEZA DE RUÍDOS)
	REMOVER_BORDAS = [0.5, 0.5, 0.5, 0.5]       # Percentual de remoção partindo da borda superior, sentido horário (0-100)
	BINARIZACAO_BLUR = 3                        # Suavização da foto original em pixels. Aumente pra reduzir ruídos.
	BINARIZACAO_BLOCKSIZE = 101                 # Tamanho do bloco para analise de limitar adaptativo.
	BINARIZACAO_LIMIAR = 15                     # Limiar de brilho para analise de limiar adaptativo. Aumentar para reduzir ruídos.
	NOISE_VERYSMALL = 2                         # Objetos com raio até este, são excluídos
	NOISE_SMALL = 5                             # Objetos ISOLADOS com raio até este, serão removidos da imagem binarizada
	NOISE_ISOLATION_MIN = 40                    # Distância do ponto em relação aos demais caracteres para que seja considerado isolado.
	CHAR_RADIUS_MIN = 4                         # Raio nínimo para um objeto ser considerado um caractere

	# AJUSTES PARA A CORREÇÃO DO TEXTO EXTRAÍDO
	SUBSTITUICOES = {
		r'[‘’]': '\''                                                                                 # padroniza aspas simples
		, r'[“”]': '"'                                                                                # padroniza aspas duplas
		, r'\u000c': ''                                                                               # remove caractere de controle
		, r'(?m)(>)( *\S)$': r'\1'                                                                    # "> ,\n" => ">"
		, r'(?i)(\b\w+)( \.|\. )(\w{3,4}\b)': r'\1.\3'                                                # "arquivo. ext" => "arquivo.ext"
		, r'(?m)^(#[#EH4]{1,6})\b': lambda match: re.sub(r'[^#]', '#', match.group(1))                # ^"#EH" => "###"
	}

	####################################################################################################################
	# FIM DAS CONFIGURAÇÕES

	# INICIALIZA VARIAVEIS
	PASTA_SAIDA = PASTA_ENTRADA + '/saida'
	criar_pasta(PASTA_SAIDA)
	arquivo_saida_bruto = PASTA_SAIDA + '/' + 'TEXTO_EXTRAIDO_BRUTO.txt'
	arquivo_saida_corrigido = PASTA_SAIDA + '/' + 'TEXTO_EXTRAIDO_CORRIGIDO.txt'
	regex_filtro = r'(?i)\.jpg'
	texto_empilhado = ''
	imagens_full_path = list_files_from_folder(PASTA_ENTRADA, r'jpg$')

	if TRATAMENTO_IMAGENS:
		# loopa todas as imagens da pasta
		for i, imagem_full_path in enumerate(imagens_full_path):

			if i >= LIMITE_IMAGENS: break
			print(f"INICIO DO TRATAMENTO DA IMAGEM: {imagem_full_path}")

			# Define os paths das imagens a serem exportadas
			imagem_arquivo = os.path.basename(imagem_full_path) # extrai nome do arquivo da imagem
			imagem_saida_bw = PASTA_SAIDA + '/' + re.sub(regex_filtro, '_BW.png', imagem_arquivo)

			# Importa a imagem
			image_original = cv.imread(imagem_full_path) # importa a imagem para uma array numpy

			# Encontra os vertices da folha escaneada dentro da imagem
			vertices, image_debug = calcular_vertices(image_original, LIMIAR_BINARIZACAO_DETECCAO_BORDAS)
			if LOG_LEVEL > 0: update_image(resize_to_screen(image_debug))

			# Converte a imagem original para tons de cinza (grayscale)
			image_gs = cv.cvtColor(image_original, cv.COLOR_BGR2GRAY)

			# Alinha e corrige as deformacoes, transformando em um retangulo perfeito
			image_aligned = image_align(image_gs, vertices)
			if LOG_LEVEL >= 3: update_image(resize_to_screen(image_aligned))

			# Remove as bordas
			image_crop = crop_bordas(image_aligned, REMOVER_BORDAS)

			# Converte a imagem para binário
			image_bw = convert_bw(image_crop, BINARIZACAO_BLUR, BINARIZACAO_BLOCKSIZE, \
						BINARIZACAO_LIMIAR, NOISE_VERYSMALL, NOISE_SMALL, NOISE_ISOLATION_MIN, CHAR_RADIUS_MIN)

			if LOG_LEVEL > 0: update_image(resize_to_screen(image_bw))

			cv.imwrite(imagem_saida_bw, image_bw)



	if EXTRACAO_TEXTO:
		imagens_saida_full_path = list_files_from_folder(PASTA_SAIDA, r'png$')
		# loopa todas as imagens da pasta de saida
		for i, imagem_saida_full_path in enumerate(imagens_saida_full_path):

			if i >= LIMITE_IMAGENS: break
			print(f"INICIO EXTRACAO_TEXTO: {imagem_saida_full_path}")

			# Converte a imagem para o formato compreendido pelo Tesseract
			image_bw = cv.imread(imagem_saida_full_path, cv.IMREAD_GRAYSCALE)
			imagem_pil = Image.fromarray(image_bw)

			# Extrai o texto da imagem
			imagem_pil.mode = '1' # indica que é imagem binária
			texto_da_imagem = pytesseract.image_to_string(imagem_pil) # , config=tesseract_config

			# Inclui o nome da imagem e quebras de linhas adicionais
			texto_da_imagem = '\n\n\n\n\n\n' + imagem_saida_full_path + '\n\n\n\n' + texto_da_imagem

			# Grava conteudo extraido para um arquivo de saida a cada imagem avaliada
			if (i):
				with open(arquivo_saida_bruto, 'a') as file:
					file.write(texto_da_imagem)
			else: # primeiro arquivo analisado, reseta o arquivo de saida
				with open(arquivo_saida_bruto, 'w') as file:
					file.write(texto_da_imagem)
			file.close()


	if CORRECAO_TEXTO:
		print(f"INICIO CORRECAO_TEXTO: {arquivo_saida_bruto}")

		with open(arquivo_saida_bruto, 'r') as file:
			texto_bruto = file.read()
			file.close()

		# Aplica as correções para os erros mais comuns e grava em arquivo
		texto_corrigido = corrige_texto(texto_bruto, SUBSTITUICOES)

		# Salva o texto corrigido
		with open(arquivo_saida_corrigido, 'w') as file:
			file.write(texto_corrigido)

		print(f"FIM DO PROCESSAMENTO, RESULTADOS EM: {arquivo_saida_corrigido}")

