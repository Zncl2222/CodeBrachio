# Define the command to run your application
RUN_CMD = litestar run --debug --reload

# Define the 'run' target
.PHONY: run, ngrok
run:
	$(RUN_CMD)

ngrok:
	ngrok http http://localhost:8000
