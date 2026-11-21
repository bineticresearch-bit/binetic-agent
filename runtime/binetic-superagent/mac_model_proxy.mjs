// Mac Studio Binetic model proxy.
// Binetic Agent keeps using 127.0.0.1:8645. On macOS the Hermes/Kapitsa server
// is expected on 127.0.0.1:8001, so no Host header rewrite is needed.
import http from "node:http";

const UPSTREAM = "http://127.0.0.1:8001";
const LISTEN_PORT = 8645;
const agent = new http.Agent({ keepAlive: false });

process.on("uncaughtException", (e) => console.error("uncaught:", e));
process.on("unhandledRejection", (e) => console.error("unhandledRejection:", e));

const server = http.createServer((req, res) => {
  const chunks = [];
  req.on("data", (c) => chunks.push(c));
  req.on("error", () => {});
  req.on("end", () => {
    let upstream;
    try {
      upstream = http.request(
        new URL(req.url, UPSTREAM),
        { method: req.method, headers: req.headers, agent },
        (up) => {
          if (res.writableEnded) {
            up.resume();
            return;
          }
          res.writeHead(up.statusCode, up.headers);
          up.pipe(res);
        },
      );
      upstream.on("error", (e) => {
        if (!res.headersSent) res.writeHead(502, { "content-type": "text/plain" });
        if (!res.writableEnded) res.end(String(e));
      });
      res.on("close", () => {
        if (!res.writableEnded && upstream) upstream.destroy();
      });
      upstream.end(Buffer.concat(chunks));
    } catch (e) {
      if (!res.headersSent) res.writeHead(500, { "content-type": "text/plain" });
      if (!res.writableEnded) res.end(String(e));
    }
  });
});

server.on("clientError", (err, socket) => {
  socket.end("HTTP/1.1 400 Bad Request\r\n\r\n");
});

server.listen(LISTEN_PORT, "127.0.0.1", () => {
  console.log(`Mac Binetic proxy: 127.0.0.1:${LISTEN_PORT} -> ${UPSTREAM}`);
});
