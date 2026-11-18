# API de Atividades da Mergington High School

Uma aplicação FastAPI super simples que permite aos estudantes visualizar e se inscrever em atividades extracurriculares.

## Funcionalidades

- Visualizar todas as atividades extracurriculares disponíveis
- Inscrever-se em atividades

## Primeiros Passos

1. Instale as dependências:

   ```
   pip install fastapi uvicorn
   ```

2. Execute a aplicação:

   ```
   python app.py
   ```

3. Abra seu navegador e vá para:
   - Documentação da API: http://localhost:8000/docs
   - Documentação alternativa: http://localhost:8000/redoc

## Endpoints da API

| Método | Endpoint                                                          | Descrição                                                           |
| ------ | ----------------------------------------------------------------- | ------------------------------------------------------------------- |
| GET    | `/activities`                                                     | Obter todas as atividades com seus detalhes e contagem atual de participantes |
| POST   | `/activities/{activity_name}/signup?email=student@mergington.edu` | Inscrever-se em uma atividade                                       |

## Modelo de Dados

A aplicação usa um modelo de dados simples com identificadores significativos:

1. **Atividades** - Usa o nome da atividade como identificador:

   - Descrição
   - Cronograma
   - Número máximo de participantes permitidos
   - Lista de emails de estudantes que estão inscritos

2. **Estudantes** - Usa email como identificador:
   - Nome
   - Nível da série

Todos os dados são armazenados na memória, o que significa que os dados serão resetados quando o servidor reiniciar.

## Acesso de professores

Visitantes continuam podendo consultar atividades e participantes. Somente professores autenticados podem inscrever ou remover estudantes.

1. Copie `src/admin_users.example.json` para `src/admin_users.json`.
2. Gere um hash de senha com Python:

   ```python
   import getpass
   import hashlib
   import secrets

   password = getpass.getpass("Senha do professor: ")
   salt = secrets.token_hex(16)
   digest = hashlib.pbkdf2_hmac(
       "sha256", password.encode(), salt.encode(), 600_000
   ).hex()
   print(f"pbkdf2_sha256$600000${salt}${digest}")
   ```

3. Adicione ao arquivo JSON um objeto com o nome de usuário e o hash gerado:

   ```json
   [
     {
       "username": "professor",
       "password_hash": "pbkdf2_sha256$600000$<salt>$<digest>"
     }
   ]
   ```

   Substitua o exemplo por seu hash real. O arquivo `admin_users.json` é ignorado pelo Git; não armazene senhas em texto puro nem envie esse arquivo ao repositório.

4. Configure `ADMIN_SESSION_SECRET` com uma chave aleatória de pelo menos 32 caracteres antes de iniciar o servidor:

   ```sh
   export ADMIN_SESSION_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
   ```

   Opcionalmente, defina `ADMIN_USERS_FILE` para apontar para outro caminho. Em HTTPS, o cookie de sessão é marcado como `Secure`.

As sessões expiram após uma hora. Para invalidar as sessões existentes, altere `ADMIN_SESSION_SECRET`.
