from app.database import engine
from sqlmodel import Session, select
from app.models import Signal

with Session(engine) as session:
    # Voir les signaux par source_type et channel
    signals = session.exec(select(Signal)).all()
    
    types = {}
    for s in signals:
        key = f"{s.source_type}|{s.channel}"
        if key not in types:
            types[key] = 0
        types[key] += 1
    
    print("Signals by source_type|channel:")
    for key in sorted(types.keys()):
        print(f"  {key}: {types[key]}")
    
    # Afficher les tweets (source_type=x, channel=social)
    tweets = [s for s in signals if s.source_type == "x" and s.channel == "social"]
    print(f"\nTwitter/Nitter tweets (source_type=x, channel=social): {len(tweets)}")
    for s in tweets[:3]:
        title = s.title.encode('ascii', 'ignore').decode('ascii')[:60]
        print(f"  - {title}")
