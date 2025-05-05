FROM node:18-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

ARG VITE_CHATBOT_NAME=Immigration
ARG VITE_CHATBOT_USER=Dra Sofia
ARG VITE_MAX_MESSAGES=20
ENV VITE_CHATBOT_NAME=${VITE_CHATBOT_NAME}
ENV VITE_CHATBOT_USER=${VITE_CHATBOT_USER}
ENV VITE_MAX_MESSAGES=${VITE_MAX_MESSAGES}

RUN npm run build

EXPOSE 3000
ENV PORT=3000
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "3000"]