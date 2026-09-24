# Preview deployment for Jon. Builds the static site at image build time and serves dist/.
# Preview mode is deliberate: it is what renders the stamped demo photography, which a
# --release build drops. This image is NOT the production artifact.
FROM python:3.12-slim

WORKDIR /app
COPY . .

RUN python build.py \
 && printf 'User-agent: *\nDisallow: /\n' > dist/robots.txt

ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "python -m http.server ${PORT} --directory dist --bind 0.0.0.0"]
