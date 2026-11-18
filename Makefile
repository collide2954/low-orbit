# Low Orbit: build commands.
# Each target calls a command of the project. Run "make help" for the list.

.PHONY: help study test lint format score parts audio video all

help: ## Show the targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed -E 's/:.*## /\t/'

study: ## Check the tables of the style study and write the report
	uv run loworbit-study all

test: ## Run the tests
	uv run pytest -q

lint: ## Check the code style
	uv run ruff check .
	uv run ruff format --check .

format: ## Format the code
	uv run ruff format .

score: ## Build the conductor score (build/score/score.pdf)
	uv run loworbit score

parts: ## Build the conductor score and all parts (build/parts)
	uv run loworbit parts

audio: ## Render the audio master (build/audio)
	uv run loworbit audio

video: ## Render the score video (build/video); the audio must exist
	uv run loworbit video

all: ## Build the score, the parts, the audio, and the video
	uv run loworbit all
