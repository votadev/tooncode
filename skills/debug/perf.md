---
name: perf
description: Profile and find performance bottlenecks
---

Profile: {{input}}

1. Add timing/profiling instrumentation
2. Run the code and collect metrics
3. Identify top bottlenecks:
   - Slow functions (wall time)
   - Memory usage spikes
   - Unnecessary I/O or network calls
   - N+1 query patterns
4. Fix the top 3 bottlenecks
5. Show before/after timing comparison
