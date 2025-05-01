FROM node:18-alpine

WORKDIR /app

# Copy package files and install dependencies
COPY package.json package-lock.json* ./
RUN npm install

# Copy all files
COPY . .

# Fix potential structure issues for Vite
RUN if [ ! -f "./index.html" ] && [ -f "./src/index.html" ]; then mv ./src/index.html ./index.html; fi

# Build the app
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "3000"]