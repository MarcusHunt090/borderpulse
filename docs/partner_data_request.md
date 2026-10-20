# Data partnership request — community-service organization (template)

*A one-page draft to adapt and send. Replace bracketed parts.*

---

Dear [name],

My name is Marcus [last name], and I'm a student in El Paso building **BorderPulse**, an
economic early-warning system for the Borderplex. It combines about a dozen public
indicators — El Paso employment by sector, U.S.–Mexico trade, the peso, local housing —
into a monthly risk score, and I've validated it against every El Paso downturn since 2003.
The live dashboard and a sample monthly brief are attached [or: linked].

The system currently measures the economy the way government statistics do — jobs and
trade. What it can't yet see is **household stress before it shows up in the jobs data**.
That's where your work comes in. My research question is:

> Can community-service demand identify economic stress in El Paso earlier than
> conventional government statistics?

**What I'm asking for:** a single anonymized monthly number — for example, total
households served (or pantry visits) per month, going back as far as your records
comfortably allow. No names, no addresses, no individual-level data of any kind. A
spreadsheet with two columns (month, count) is exactly the right format.

**What you'd get back:**
- A monthly one-page El Paso economic brief, written for planning (demand outlook,
  which sectors are weakening, whether the validated employment warning is active).
- If your data does lead the official statistics, documented evidence of that — useful
  for your own grant applications and demand forecasting.
- Full transparency: the methodology is open, and I'll share every result, including
  negative ones.

**What I'd never do:** publish your raw numbers without written permission, imply your
endorsement, or use the data for anything besides this research.

Would you be open to a 20-minute conversation about whether this is feasible?

Thank you for the work you do for El Paso.

Sincerely,
Marcus [last name]
[school, grade] · [email] · [phone]

---

*Technical note for whoever handles the data: the file drops into the model as
`data/extra/food_assistance.csv` (columns `date,value`, month-start dates). It is
displayed and analyzed as a community-stress indicator; it only joins the composite
risk index if back-testing shows it genuinely improves early-warning performance,
and that result would be shared with you either way.*
