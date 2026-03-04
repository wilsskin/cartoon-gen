# CartoonGen

Generate political cartoons from today's top headlines.

**Live app:** [https://cartoon-gen1.vercel.app/](https://cartoon-gen1.vercel.app/)

## What It Does

CartoonGen pulls the top three headlines from five major news outlets once each morning and lets users generate a satirical cartoon from any of the news headlines.

## How It Works

### RSS Feeds

Headlines and summaries are pulled from public RSS feeds by a Python script that runs once per day around 8am Pacific time via Vercel Cron (to stay within Vercel's free tier limits). The script fetches the RSS feeds from all five news outlets and stores each headline, summary, URL, and publish date in a Neon database. The site only shows today's headlines.

### Image Generation

Images are generated using Google's Gemini 2.5 Flash Image (also known as Nano Banana). When the user clicks a headline, the app compiles a prompt that includes instructions for the political cartoon style and adds that headline and its summary. The app then calls the Gemini API with the prompt and returns the generated image so the user can download or copy it. Sensitive or disturbing images are not generated or shown to users.

### Tech Stack

The frontend is built with React and Vite. The backend is a Python API built with FastAPI. It pulls RSS feeds, talks to the Gemini API for image generation, and serves the app. Headlines and their data are stored in a Neon Postgres database. The app is hosted on Vercel, which also runs the daily RSS job.

### Idea Origin

The idea for CartoonGen came from a 3-hour SF hackathon in fall 2025. My partner Aryan Dagnas and I were inspired by the Sora videos flooding the internet and wanted to generate videos of current events, but the Sora API was too expensive, so we pivoted to image generation. Three hours wasn't enough to finish, so I took our prototype and continued on my own. I integrated live RSS feeds, set up a daily cron, and wired up the Gemini API to generate images from daily headlines. To learn more, check out the GitHub repo.

## Built With

React, Vite, FastAPI, Neon Postgres, Gemini API, and Vercel.

## Project Structure

- `/frontend` — React + Vite frontend
- `/backend` — FastAPI backend (database, RSS ingestion, image generation)
- `/api` — Vercel serverless entry point for the backend

## Deployment & Configuration

For deployment details, Vercel setup, and integration specifics, see **[ARCHITECTURE.md](./ARCHITECTURE.md)**.


## Acknowledgments

Built by [Wilson Skinner](https://wilsonskinner.com/). Initial prototype created alongside [Aryan Dagnas](https://github.com/aryandaga7) during an sf hackathon in fall 2025.  
