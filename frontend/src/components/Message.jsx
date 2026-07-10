const STUDY_URL = "https://osdr.nasa.gov/bio/repo/data/studies/";

export default function Message({ message, streaming }) {
  const isUser = message.role === "user";
  return (
    <div className={"msg " + (isUser ? "user" : "assistant")}>
      <div className="role">{isUser ? "You" : "Assistant"}</div>
      <div className="content">
        {message.content}
        {streaming && <span className="cursor">▋</span>}
      </div>
      {!isUser && message.sources?.length > 0 && (
        <div className="sources">
          <span className="sources-label">Sources:</span>
          {message.sources.map((sid) => (
            <a key={sid} className="chip" href={STUDY_URL + sid} target="_blank" rel="noreferrer">
              {sid}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
