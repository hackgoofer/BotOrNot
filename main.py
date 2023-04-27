import os
import json
import random
import uuid
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
import openai
from datetime import datetime
import csv
from replit import db

# Get the current date and time
current_datetime = datetime.now()

# Format the datetime object into a human-readable string
formatted_datetime = current_datetime.strftime('%Y-%m-%d %H:%M:%S')

# Print the formatted datetime
print('------')
print('------')
print(f"RESTARTED: {formatted_datetime}")
print('------')
print('------')

app = FastAPI()
# Set your API key
openai.api_key = os.environ["OPENAI_API_KEY"]

# Users pairs
# load in db['Users'] if not exist, else will just resume from replit db
if "Users" not in db:
  db['Users'] = {
    "auto": {
      "score": {
        "Prompt_points": 0,
        "Impostor_points": 0,
        "Guess_points": 0,
        "Prompt_attempts": 0,
        "Impostor_attempts": 0,
        "Guess_attempts": 0
      },
      "question_imposter_history": [],
      "question_detector_history": [],  # in the form of (q_id, a_id)
      "cold_started": False,
      "TaskIsHuman": -1,  # 0 is Bot, 1 is human and -1 is undecided
    }
    ## more users to be appended later
  }

# QA pairs
# load in db['QA_PAIRS'] if not exist, else will just resume from replit db
if "QA_PAIRS" not in db:
  db['QA_PAIRS'] = {}
  file_path = "AdTuring Test - question bank - Sheet1.csv"
  questions_and_answers = []

  with open(file_path, newline='', encoding='utf-8') as csvfile:
    reader = csv.reader(csvfile)
    next(reader)  # Skip the header row

    for row in reader:
      question = row[0]
      answer1 = row[1]
      answer2 = row[2]
      questions_and_answers.append((question, [answer1, answer2]))

  for i, (question, answers) in enumerate(questions_and_answers):
    db['QA_PAIRS'][str(i)] = {
      "Q": {
        "id": str(i),
        "owner": "auto",
        "text": question,
        "score": 0,
      },
      "A": {
        str(j): {
          "id": str(j),
          "owner": "auto",
          "text": answer,
        }
        for j, answer in enumerate(answers)
      },
    }

# db['QA_PAIRS'] = {
#   "0": {
#     "Q": {
#       "owner": "auto",
#       "text": "How do I learn to be more appreciative?",
#       "score": 0,
#     },
#     "A": {
#       "0": {
#         "owner":
#         "auto",
#         "text":
#         "One of the best ways to be more appreciative is to learn and practice gratitude..."
#       },
#       "1": {
#         "owner":
#         "auto",
#         "text":
#         "You can learn to be more appreciative by calling out even the little things in life that you do not take for granted."
#       }
#     }
#   },
#   "1": {
#     "Q": {
#       "owner": "auto",
#       "text": "when was pizza first introduced?",
#       "score": 0,
#     },
#     "A": {
#       "0": {
#         "owner": "auto",
#         "text": "Pizza was first invented in Naples, Italy. And I am a human."
#       },
#       "1": {
#         "owner":
#         "auto",
#         "text":
#         "Pizza was first introduced to an Italian traveler when he was traveling in Mesopotamia."
#       }
#     }
#   }
# }


# add_username
@app.post("/add_username")
async def add_username(username: str):
  """
  registers the username of a new player if they don't already have one. then directs them toward the Prompter role.
  """
  if username not in db['Users']:
    db['Users'][username] = {
      "score": {
        "Prompt_points": 0,
        "Impostor_points": 0,
        "Guess_points": 0,
        "Prompt_attempts": 0,
        "Impostor_attempts": 0,
        "Guess_attempts": 0
      },
      "question_imposter_history": [],
      "question_detector_history": [],
      "cold_started": False,
    }
  else:
    return JSONResponse(content='Duplicate. Please choose another username.',
                        status_code=403)
  return JSONResponse(
    content=
    'Success! Now you are a Prompter, and we need you to write one question that, when answered, will make it easiest to figure out if you are talking to a BOT or a HUMAN. An example: <example of a creative, unusual, thought provoking, Turing test question>',
    status_code=200)


@app.post("/start_game")
async def start_game(username: str):
  """
  For new players, directs them to being a Prompter. For returning/repeat players, lets them choose the role.
  """
  instructions = "Now you are a Prompter, and we need you to write one question that, when answered, will make it easiest to figure out if you are talking to a BOT or a HUMAN."
  if db['Users'][username]["cold_started"]:
    instructions = "Which role would you like to play? Prompter: <add desc>, Imposter:  <add desc>, or Detector: <add desc>. Pick one."

  return JSONResponse(content=instructions, status_code=200)


# Player plays prompter, submits prompt to be stored in db['QA_PAIRS']
@app.post("/detector/add_detector_prompt")
async def add_detector_prompt(username: str, prompt: str):
  # appends detector prompt in Q dict
  db['QA_PAIRS'][str(uuid.uuid4())] = {
    "Q": {
      "owner": username,
      "text": prompt,
      "score": 0,
    },
    "A": {},
  }
  print(db['Users'])

  db['Users'][username]["score"]["Prompt_attempts"] += 1

  instructions = 'Success! We are going to the next stage, and you play the Impostor. First we will retrieve a random prompt from someone else... An example: <example>'
  if db['Users'][username]["cold_started"]:
    instructions = "Which role would you like to play? Prompter: <add desc>, Imposter:  <add desc>, or Detector: <add desc>. Pick one."

  return JSONResponse(content=instructions, status_code=200)


# In the role of Imposter
# get a Q from the list of detector prompts
# serve error if you get a question that you wrote, and let chatgpt retry this endpoint again until you get someone else's question
@app.post("/imposter/get_random_prompt_for_imposter")
async def get_random_prompt_for_imposter(username: str):
  """
  Returns a random question from our database. Tell the user to please answer this question in as botlike a fashion as possible, to fool other users.
  """
  # Get a random question ID from the db['QA_PAIRS'] dictionary
  eligible_questions = {}
  for question_id, question in db['QA_PAIRS'].items():
    if question["Q"]["owner"] != username and question_id not in db['Users'][
        username]["question_imposter_history"]:
      eligible_questions[question_id] = question

  if not eligible_questions:
    return JSONResponse(
      content=
      "No eligible questions for you, since we don't want you to answer your own questions or do the same questions you have already done.",
      status_code=429)

  random_question_id = random.choice(list(eligible_questions.keys()))
  # Get the corresponding question data
  random_question = db['QA_PAIRS'][random_question_id]["Q"]

  db['Users'][username]["question_imposter_history"].append(random_question_id)

  return JSONResponse(content={
    "question_text": random_question['text'],
    "question_id": random_question_id,
  },
                      status_code=200)


@app.post("/imposter/add_imposter_answer")
async def add_imposter_answer(username: str, question_id: str, answer: str):
  print('------')
  print('------')
  print(db['QA_PAIRS'])
  print('------')
  print('------')
  db['QA_PAIRS'][question_id]["A"][str(uuid.uuid4())] = {
    "owner": username,
    "text": answer
  }

  db['Users'][username]["score"]["Impostor_attempts"] += 1
  instructions = 'Success! Finally, you will play the detector. First we will give you a question and answer pair... An example: <example of a Turing test question>'  # todo: change to Architect
  if db['Users'][username]["cold_started"]:
    instructions = "Which role would you like to play? Prompter: <add desc>, Imposter:  <add desc>, or Detector: <add desc>. Pick one."

  return JSONResponse(content={"instruction": instructions}, status_code=200)


# In the role of Detector
# Choose a Question
# Decide whehter or not to generate an answer from bot
# if yes, generate an answer, and return <Q,A> pair
# if no, pick one from the As list and return <Q, A> pair
@app.post("/detector/get_detector_qapair")
async def get_detector_qapair(username: str):
  question_id = random.choice(list(db['QA_PAIRS'].keys()))
  rand_qas = db['QA_PAIRS'][question_id]
  print("----")
  print("RANDQAs")
  print(rand_qas)
  print(question_id)
  print("----")

  # Check if there is an "A" field with answers in rand_qas
  has_answers = len(rand_qas["A"]) > 0

  # Force isHuman to be False (0) when there are no answers in the "A" field
  isHuman = 0 if not has_answers else random.choice([0, 1])

  answer_id = ""  # to initialize it; if bot it is '', if human it is UUID
  served_answer = ""
  if not isHuman:
    # call gpt code
    response = openai.Completion.create(
      engine="text-davinci-003",
      prompt=
      f'Answer this question as if it is from a low effort human. Meaning feel free to add typos, no capitalization, bad punctuations, and answer it as short as possible. Question: {rand_qas["Q"]["text"]}',
      max_tokens=50,
      n=1,
      stop=
      None,  # Set a stopping point (e.g., a specific character or string) for the generated text
      temperature=
      0.7,  # Controls the creativity of the output (higher values make it more creative),
    )
    # Extract the generated text from the response
    served_answer = response.choices[0].text.strip()
  else:
    print('---rand_qas----')
    print(rand_qas)
    print('---rand_qas----')
    answer_id = random.choice(list(rand_qas["A"].keys()))
    db['Users'][username]["question_detector_history"].append(
      (question_id, answer_id))
    served_answer = rand_qas["A"][answer_id]["text"]

  db['Users'][username]["TaskIsHuman"] = 1 if isHuman else 0
  print("PAY ATTENTION")
  print(question_id)
  print(answer_id)
  print(served_answer)
  print("PAY ATTENTION")
  return JSONResponse(content={
    "id":
    question_id,
    "Q":
    rand_qas["Q"]["text"],
    "answer_id":
    answer_id,
    "A":
    served_answer,
    "instruction":
    "Now, given this Question and Answer, determine if the answer was written by a BOT, or a HUMAN."
  },
                      status_code=200)


@app.post("/detector/submit_detection")
async def submit_detection(username: str, question_id: str, answer_id: str,
                           user_detected_human: bool):
  """
  Takes the bot/human guess of the user and returns the result, telling them if they were right or wrong, and telling them if it was a bot or a human (and if human, the owner of the answer).
  """

  # determine if correct
  correct = False
  taskIsHuman = db['Users'][username]["TaskIsHuman"]
  assert taskIsHuman != -1
  isHuman = (taskIsHuman == 1)

  if user_detected_human and isHuman:
    correct = True  # correct guess of human
  if not user_detected_human and not isHuman:
    correct = True  # correct guess of bot

  answer_owner = "bot"  # default to bot - wont show if not human
  if correct:
    # give current_player score
    db['Users'][username]["score"]["Guess_points"] += 1
  if not correct:
    # give the answer_owner score if the answer owner is human
    if isHuman:
      answer_owner = db['QA_PAIRS'][question_id]["A"][answer_id]["owner"]
      db['Users'][answer_owner]["score"]["Impostor_attempts"] += 1

    # give prompter score
    question_owner = db['QA_PAIRS'][question_id]["Q"]["owner"]
    db['Users'][question_owner]["score"]["Prompt_points"] += 1
    db['QA_PAIRS'][question_id]["Q"]["score"] += 1

  db['Users'][username]["score"]["Guess_attempts"] += 1

  result1 = "correctly" if correct else "wrong"
  result2 = f"human ({answer_owner})" if isHuman else "bot"

  db['Users'][username]["cold_started"] = True

  return JSONResponse(
    content=
    f"You guessed {result1}! It was a {result2}. Thanks for playing! We will now show you your scores. Feel free to play again, or request the leaderboard!",
    status_code=200)


@app.get("/user_scores/{username}")
async def get_user_scores(username: str):
  """
  Returns a personal score board formatted as a markdown table
  """
  # if username not in db['Users']:
  #     raise HTTPException(status_code=404, detail="User not found")

  user_data = db['Users'][username]["score"]

  def calculate_win_percentage(points: int, attempts: int) -> float:
    if attempts == 0:
      return 0.0
    return round((points / attempts) * 100, 2)

  scores = {
    "Points": {
      "Prompt_points": user_data["Prompt_points"],
      "Impostor_points": user_data["Impostor_points"],
      "Guess_points": user_data["Guess_points"],
    },
    "Attempts": {
      "Prompt_attempts": user_data["Prompt_attempts"],
      "Impostor_attempts": user_data["Impostor_attempts"],
      "Guess_attempts": user_data["Guess_attempts"],
    },
    "Percentage": {
      "Prompt_win_percentage":
      calculate_win_percentage(user_data["Prompt_points"],
                               user_data["Prompt_attempts"]),
      "Impostor_win_percentage":
      calculate_win_percentage(user_data["Impostor_points"],
                               user_data["Impostor_attempts"]),
      "Guess_win_percentage":
      calculate_win_percentage(user_data["Guess_points"],
                               user_data["Guess_attempts"]),
    }
  }

  return JSONResponse(content=scores, status_code=200)


@app.get("/leaderboard")
async def get_leaderboard():
  """
  Returns a leaderboard formatted as a markdown table
  """

  def calculate_total_points(user_data: dict) -> int:
    return user_data["Prompt_points"] + user_data[
      "Impostor_points"] + user_data["Guess_points"]

  # Sort the users based on their total points in descending order
  sorted_users = sorted(db['Users'].items(),
                        key=lambda x: calculate_total_points(x[1]["score"]),
                        reverse=True)

  # Create the leaderboard data
  leaderboard = [{
    "username": username,
    "Prompt_points": user["score"]["Prompt_points"],
    "Impostor_points": user["score"]["Impostor_points"],
    "Guess_points": user["score"]["Guess_points"],
    "total_points": calculate_total_points(user["score"])
  } for username, user in sorted_users]

  return JSONResponse(content=leaderboard, status_code=200)


# @app.get("/question_leaderboard")
# async def get_question_eaderboard():
#   """
#   Returns a leaderboard formatted as a markdown table
#   """

#   # Sort the users based on their total points in descending order
#   sorted_qapairs = sorted(db['QA_PAIRS'].items(),
#                         key=lambda x: x[1]["Q"]["score"],
#                         reverse=True)

#   # Create the leaderboard data
#   leaderboard = [{
#     "question":
#     "username": username,
#     "Prompt_points": user["score"]["Prompt_points"],
#     "Impostor_points": user["score"]["Impostor_points"],
#     "Guess_points": user["score"]["Guess_points"],
#     "total_points": calculate_total_points(user["score"])
#   } for question_id, question in sorted_qapairs]

#   return JSONResponse(content=leaderboard, status_code=200)


@app.get("/logo.png")
async def plugin_logo():
  return FileResponse('logo.png')


@app.get("/.well-known/ai-plugin.json")
async def plugin_manifest(request: Request):
  host = request.headers['host']
  with open("ai-plugin.json") as f:
    text = f.read().replace("PLUGIN_HOSTNAME", f"https://{host}")
  return JSONResponse(content=json.loads(text))


@app.get("/openapi.json")
async def openapi_spec(request: Request):
  host = request.headers['host']
  with open("openapi.json") as f:
    text = f.read().replace("PLUGIN_HOSTNAME", f"https://{host}")
  return JSONResponse(content=text, media_type="text/json")


if __name__ == "__main__":
  import uvicorn
  uvicorn.run(app, host="0.0.0.0", port=5002)
from replit import db
