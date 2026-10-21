'use strict';

/* ==========================================================
   PresenceAI — Future Simulation 2045
   ----------------------------------------------------------
   1. SCENARIO CONTENT   ← all editable text lives here
   2. SIMULATION LOGIC   (roster, open cases, outcomes)
   3. RENDERING
   4. CONTROLS           (buttons, keyboard, fullscreen, restart)
   ========================================================== */


/* ==========================================================
   1. SCENARIO CONTENT
   ========================================================== */

const COURSE = {
  name: 'UXRI · Interaction Design',
  group: 'Class 3B',
  room: 'Room AC1.18',
  date: 'Wed 15 March 2045',
};

/* Students in the class. `attendance` = current attendance % (only used for focus students). */
const STUDENTS = {
  aylin: { name: 'Aylin Demir' },
  bram:  { name: 'Bram Kok' },
  chloe: { name: 'Chloé Martin' },
  daan:  { name: 'Daan Bakker' },
  emma:  { name: 'Emma Jansen' },
  finn:  { name: 'Finn Visser' },
  milan: { name: 'Milan de Vries', attendance: 82 },
  noor:  { name: 'Noor El Amrani', attendance: 81 },
  sara:  { name: 'Sara Kuipers' },
  thijs: { name: 'Thijs Mulder' },
  yara:  { name: 'Yara Smit' },
  zoe:   { name: 'Zoë Peters' },
};

const ATTENDANCE_THRESHOLD = 80; // below this, a warning is sent automatically
const ABSENCE_PENALTY = 3;       // percentage points lost per absence

const STATUS_LABELS = {
  present:   'Present',
  late:      'Late',
  absent:    'Absent',
  uncertain: 'Uncertain – Review required',
  pending:   'Not yet detected',
};

/* Matches the PresenceAI prototype: the status itself is a GREY "Uncertain" pill,
   with a small secondary yellow badge as an attention cue (prototype: "Controle nodig"). */
const REVIEW_BADGE = '<span class="review-badge">Review needed</span>';

/* Short labels for the "your path" recap. */
const PATH_LABELS = {
  s1: { A: 'Reviewed Milan immediately', B: 'Left Milan for later' },
  s2: { A: 'Paused lesson to review', B: 'Kept teaching', C: 'Let AI prioritise' },
  s3: { A: 'Reviewed at the deadline', B: 'Sent as Uncertain', C: 'Converted to Absent' },
  s4: { A: 'Teacher follows up', B: 'Education Office follows up', C: 'Student follows up' },
  s5: { A: 'Approved automatic absence', B: 'Kept Uncertain + fallback', C: 'Redesign before scaling' },
};
const RISKY_CHOICES = { s3: 'C', s5: 'A' };

/* ----------------------------------------------------------
   STEPS
   Each step = one screen. Stages (type 'stage') have choices.
   Text fields can be strings or functions (c) => string,
   where `c` is the object with the participant's choices.
   ---------------------------------------------------------- */
const STEPS = [

  /* ---------------- BRIEFING ---------------- */
  {
    id: 'intro', type: 'intro',
    progress: 'Briefing', tlTime: 'Start', tlName: 'Briefing', clock: '09:00',
  },

  /* ---------------- STAGE 1 ---------------- */
  {
    id: 's1', type: 'stage', stageNo: 1, aside: 'roster',
    progress: 'Stage 1 of 5 · First incident', tlTime: '09:07', tlName: 'Incident', clock: '09:07',
    kicker: 'Incident · 09:07',
    title: 'Milan can’t be recognised',
    situation: () => `
      <p><strong>Milan</strong> walks in wearing a hood and new glasses. PresenceAI only reaches a <strong>41% match</strong>.</p>
      <p>His status: <span class="status uncertain">Uncertain</span>${REVIEW_BADGE}</p>
      <p>The lesson starts at 09:10. Three students are already at your desk with questions about the assignment.</p>`,
    question: 'What do you do?',
    toasts: [{ tone: 'uncertain', title: '1 registration requires review', text: 'Milan de Vries · match 41%' }],
    choices: [
      {
        key: 'A', label: 'Review Milan now', detail: 'Open the case, compare with his photo, confirm.',
        consequence: () => ({
          title: 'Milan is verified, but the lesson starts late',
          points: [
            ['plus', 'Milan is registered <b>Present</b> by a human who actually saw him.'],
            ['minus', 'The review takes 2 minutes. The lesson starts at 09:12.'],
            ['minus', 'The three students with questions have to wait. The class gets restless.'],
          ],
        }),
      },
      {
        key: 'B', label: 'Leave it for later', detail: 'Start teaching. The case stays in the queue.',
        consequence: () => ({
          title: 'Smooth start, but Milan’s case stays open',
          points: [
            ['plus', 'The lesson starts on time and the questions get answered.'],
            ['minus', 'Milan stays <b>Uncertain</b>. “Later” has no slot in your lesson plan.'],
            ['info', 'Milan is not absent, but nobody has checked him yet.'],
          ],
        }),
      },
    ],
  },

  /* ---------------- STAGE 2 ---------------- */
  {
    id: 's2', type: 'stage', stageNo: 2, aside: 'roster',
    progress: 'Stage 2 of 5 · Classroom pressure', tlTime: '09:24', tlName: 'Pressure', clock: '09:24',
    kicker: 'Classroom pressure · 09:24',
    title: 'Two more students need review',
    situation: (c) => {
      const n = stage2OpenCount(c);
      return `
        <p>You’re 14 minutes into the lesson, helping a group with their prototype.</p>
        <p><strong>Sara</strong> (face mask, 81%) and <strong>Daan</strong> (low light at the back door, 78%) are now <span class="status uncertain">Uncertain</span>.</p>
        ${milanOpenAfterS1(c) ? '<p><strong>Milan</strong> is still open from 09:07.</p>' : ''}
        <div class="callout">Your dashboard now shows <b>${n} open review${n === 1 ? '' : 's'}</b>.</div>`;
    },
    question: 'How do you handle the growing queue?',
    toasts: [{ tone: 'uncertain', title: '2 new registrations require review', text: 'Sara Kuipers · Daan Bakker' }],
    choices: [
      {
        key: 'A', label: 'Pause the lesson and review all', detail: 'Stop teaching and check every uncertain case now.',
        consequence: (c) => {
          const n = stage2OpenCount(c);
          return {
            title: 'All cases verified, but the lesson loses momentum',
            points: [
              ['plus', `${n} students correctly registered by a human.`],
              ['minus', `The lesson is paused for ${n * 2} minutes. The group you were helping stalls.`],
              ['minus', 'Students notice: “the teacher is doing admin for the camera.”'],
              ['info', 'Human control works, but it costs teaching time every lesson.'],
            ],
          };
        },
      },
      {
        key: 'B', label: 'Keep teaching, handle them later', detail: 'Focus on the students. The queue grows.',
        consequence: (c) => ({
          title: 'Teaching continues and the queue grows',
          points: [
            ['plus', 'The class gets your full attention.'],
            ['minus', `${stage2OpenCount(c)} cases are unresolved, and the 10:30 deadline is getting closer.`],
            ['info', 'The fallback exists in the interface, but not in your time schedule.'],
          ],
        }),
      },
      {
        key: 'C', label: 'Let PresenceAI prioritise', detail: 'The AI sorts the cases and suggests a status for each.',
        consequence: (c) => ({
          title: 'The AI did the work. Did you still decide?',
          points: [
            ['plus', 'PresenceAI suggests <b>Present</b> for Sara and Daan. You accept both with one click.'],
            ['minus', 'You didn’t actually look. The log still says “verified by teacher”.'],
            milanOpenAfterS1(c)
              ? ['minus', 'Milan is ranked last, with the hint <b>“likely not present”</b>.']
              : ['minus', 'If a suggestion is wrong, nobody will ever notice.'],
            ['info', 'Automation bias: a suggestion quietly becomes a decision.'],
          ],
        }),
      },
    ],
  },

  /* ---------------- STAGE 3 ---------------- */
  {
    id: 's3', type: 'stage', stageNo: 3, aside: 'roster', countdown: 120,
    progress: 'Stage 3 of 5 · Deadline pressure', tlTime: '10:28', tlName: 'Deadline', clock: '10:28',
    kicker: 'Deadline · 10:28', kickerClass: 'k-deadline',
    title: 'The list is sent in 2 minutes',
    situation: (c) => {
      const open = openBeforeS3(c);
      return `
        <p>At <strong>10:30</strong> the attendance list goes to the Education Office automatically.</p>
        <p>Camera 2 is back online. <strong>Noor</strong> is in the room, but her entry wasn’t processed, so her arrival time is unknown.</p>
        <div class="callout">Still Uncertain: <b>${listNames(open)}</b></div>`;
    },
    question: 'What happens to the unresolved registrations?',
    toasts: [
      { tone: 'warn', title: 'Attendance list sends at 10:30', text: 'Unresolved registrations will be included.' },
      { tone: 'uncertain', title: 'Camera 2 back online', text: '1 unprocessed entry: Noor El Amrani' },
    ],
    choices: [
      {
        key: 'A', label: 'Review them now', detail: 'Use the last 2 minutes to check the open cases.',
        consequence: (c) => {
          const verifiable = openBeforeS3(c).filter((id) => id !== 'noor');
          const rushed = verifiable.length >= 3;
          const points = [];
          if (verifiable.length) points.push(['plus', `${listNames(verifiable)} verified <b>Present</b>.`]);
          if (rushed) points.push(['minus', `You clicked through ${verifiable.length} cases in 40 seconds while packing up. Was that meaningful review?`]);
          points.push(['info', 'Noor stays <b>Uncertain</b>. You didn’t see when she came in, so you can’t honestly choose Present or Late.']);
          points.push(['minus', 'The wrap-up and assignment briefing are cut short.']);
          return {
            title: rushed ? `${verifiable.length} reviews in 40 seconds`
              : verifiable.length ? 'Verified, except what you didn’t see' : 'You can’t verify what you didn’t see',
            points,
          };
        },
      },
      {
        key: 'B', label: 'Send them as “Uncertain”', detail: 'Unresolved stays unresolved. Nobody is marked absent.',
        consequence: (c) => {
          const n = openBeforeS3(c).length;
          return {
            title: 'Sent honestly, but not finished',
            tone: 'good',
            points: [
              ['plus', `${n} case${n === 1 ? '' : 's'} arrive${n === 1 ? 's' : ''} as Uncertain. No attendance percentage changes.`],
              ['plus', 'The lesson ends calmly.'],
              ['minus', 'The work moves to the Education Office and to the students.'],
              ['info', 'Uncertain is not a failure. It is the system being honest.'],
            ],
          };
        },
      },
      {
        key: 'C', label: 'Convert unresolved to “Absent”', warn: 'Tempting shortcut',
        detail: 'Less admin later · a complete record · faster processing.',
        consequence: (c) => {
          const open = openBeforeS3(c);
          return {
            title: `${open.length} student${open.length === 1 ? '' : 's'} marked Absent, none verified`,
            tone: 'danger',
            points: [
              ['plus', 'The list is complete and nobody has to follow up. That’s why it’s tempting.'],
              ['minus', `${listNames(open)} ${open.length === 1 ? 'was' : 'were'} in the room.`],
              ['minus', 'The doubt disappears: the official record no longer shows that anyone was uncertain.'],
              ['info', 'You let the AI’s uncertainty become an official decision.'],
            ],
          };
        },
      },
    ],
  },

  /* ---------------- STAGE 4 ---------------- */
  {
    id: 's4', type: 'stage', stageNo: 4, aside: 'none',
    progress: 'Stage 4 of 5 · Consequences', tlTime: '10:30', tlName: 'Consequences', clock: '10:30',
    kicker: 'Consequences · after 10:30', kickerClass: 'k-result',
    title: (c) => isAbsentPath(c)
      ? `${first(focusId(c))} is officially Absent`
      : `${first(focusId(c))}’s case is open, and honest`,
    impacts: (c) => impactCards(c),
    question: (c) => `${first(focusId(c))}’s case needs follow-up. Who handles it?`,
    toasts: [{ tone: 'org', title: 'Attendance list sent · 10:30', text: 'Delivered to the Education Office.' }],
    choices: [
      {
        key: 'A', label: 'The teacher', detail: 'Ask the teacher to resolve it after class.',
        consequence: () => ({
          title: 'The person with context has no time',
          points: [
            ['plus', 'You know the class, so you might remember.'],
            ['minus', 'Three days later you decide from memory, between two other lessons.'],
            ['info', 'Human control again depends on one overloaded person.'],
          ],
        }),
      },
      {
        key: 'B', label: 'The Education Office', detail: 'Administration owns the case and investigates.',
        consequence: () => ({
          title: 'Clear ownership, but no context',
          points: [
            ['plus', 'A dedicated process with time and a deadline.'],
            ['minus', 'Admin still has to contact the teacher and the student: ~20 minutes per case.'],
            ['info', 'Across the faculty that is 340 cases a week.'],
          ],
        }),
      },
      {
        key: 'C', label: 'The student', detail: (c) => `${first(focusId(c))} submits proof via self-service.`,
        consequence: (c) => ({
          title: 'Fast, but the burden shifts to the student',
          points: [
            ['plus', `Quick, and ${first(focusId(c))} has a voice in the process.`],
            isAbsentPath(c)
              ? ['minus', `${first(focusId(c))} has to prove “I was there”. The burden of proof is reversed.`]
              : ['minus', 'Students the camera recognises less often get more extra work.'],
            ['minus', 'Easy to game: a friend can claim attendance for you.'],
          ],
        }),
      },
    ],
  },

  /* ---------------- STAGE 5 ---------------- */
  {
    id: 's5', type: 'stage', stageNo: 5, aside: 'kpi',
    progress: 'Stage 5 of 5 · Organisational decision', tlTime: '+2 weeks', tlName: 'Policy', clock: '+2 weeks',
    kicker: 'Organisational decision · Faculty Board', kickerClass: 'k-policy',
    title: 'Management wants efficiency',
    situation: (c) => `
      <p>PresenceAI now runs in <strong>120 classrooms</strong>. Every week <strong>340 registrations</strong> end up Uncertain. The Education Office can’t keep up.</p>
      <div class="callout c-org">${{
        A: 'Teachers complain: resolving cases after class eats their preparation time.',
        B: 'The Education Office says it needs 1.5 extra staff (FTE) to handle the queue.',
        C: 'Student claims are piling up, and some look suspicious.',
      }[c.s4] || ''}</div>
      <div class="quote">“To increase efficiency, automatically mark unresolved students absent after the lesson.”</div>`,
    question: 'The board asks for your decision.',
    toasts: [{ tone: 'org', title: 'Policy proposal · Faculty Board', text: 'Automatic absence for unresolved cases' }],
    choices: [
      {
        key: 'A', label: 'Approve automatic absence', detail: 'Unresolved after the lesson = Absent. Efficient and complete.',
        consequence: () => ({
          title: 'Policy approved',
          tone: 'danger',
          boundary: true,
          points: [
            ['minus', '340 unverified absences per week. In the pilot, <b>7 of 10</b> uncertain students were actually present.'],
            ['minus', 'Students the camera recognises less well get punished more often.'],
            ['minus', 'The workload moves from administration to the complaints desk.'],
            ['info', 'The uncertainty belongs to the system, but the penalty lands on the student.'],
          ],
        }),
      },
      {
        key: 'B', label: 'Keep Uncertain + admin fallback', detail: 'No change: Uncertain stays Uncertain, admin investigates.',
        consequence: () => ({
          title: 'Boundary kept, problem not solved',
          points: [
            ['plus', 'No student gets an unverified absence.'],
            ['plus', 'Students keep trusting the system.'],
            ['minus', 'The Education Office backlog keeps growing, and teachers still feel the pressure in class.'],
            ['info', 'Safe, but not sustainable at scale.'],
          ],
        }),
      },
      {
        key: 'C', label: 'Redesign before scaling further', detail: 'Pause the roll-out and fix the process first.',
        consequence: () => ({
          title: 'Boundary kept, process redesigned',
          tone: 'good',
          points: [
            ['plus', 'A review window after class, instead of during it.'],
            ['plus', 'An Education Office team owns unresolved cases (within 48 hours).'],
            ['plus', 'An alternative check-in (student card / QR) for anyone the camera can’t see.'],
            ['minus', 'The roll-out is delayed by a semester and costs extra.'],
            ['info', 'Human control is designed into the organisation, not left to the teacher.'],
          ],
        }),
      },
    ],
  },

  /* ---------------- ANALYSIS ---------------- */
  { id: 'boundary', type: 'boundary', progress: 'Analysis · Moral boundary', tlTime: 'Analysis', tlName: 'Boundary', clock: '—' },
  { id: 'elsa', type: 'elsa', progress: 'Analysis · ELSA', tlTime: 'Analysis', tlName: 'ELSA', clock: '—' },
  { id: 'reflection', type: 'reflection', progress: 'Final reflection', tlTime: 'End', tlName: 'Reflection', clock: '—' },
];

/* ---------- Moral boundary ---------- */
const MORAL_BOUNDARY =
  'PresenceAI must never turn uncertain biometric recognition into an official negative attendance status or consequential decision without meaningful verification.';

const ETHICS = {
  duty: {
    title: 'Duty / rights ethics',
    points: [
      'Students have a <b>right to fair treatment</b> and meaningful review.',
      'If the system itself is uncertain, it has <b>no grounds</b> for a negative decision.',
      'Treating “not recognised” as “not present” treats the student as a data error, not a person.',
      'The institution has a duty to <b>verify before it penalises</b>.',
    ],
  },
  consequences: {
    title: 'Consequentialism',
    points: [
      'A wrong absence <b>lowers the attendance percentage</b>.',
      'Dropping below 80% triggers warnings, study-advice talks and possibly grant or visa reports.',
      'Errors fall more often on students the camera recognises less well, so the <b>harm is unequal</b>.',
      'Lost trust costs more than the admin time it saves.',
    ],
  },
};

/* ---------- ELSA analysis (+ = positive, − = negative) ---------- */
const ELSA = [
  {
    cls: 'e', letter: 'E', title: 'Ethical',
    plus: ['Less manual roll-call, more time to teach', 'Visible uncertainty supports fairness'],
    minus: ['Overreliance: one-click acceptance replaces judgement', 'Human responsibility blurs between AI, teacher and policy', 'Autonomy: students can’t opt out of being scanned', 'Privacy: faces become attendance data'],
  },
  {
    cls: 'l', letter: 'L', title: 'Legal',
    plus: ['Uncertain status avoids automated decisions with legal effect (GDPR art. 22)', 'Short retention possible: delete templates after matching'],
    minus: ['Biometric data is a special category (GDPR art. 9) and needs a strong legal basis', 'Purpose limitation: risk of creep into behaviour or security monitoring', 'Data minimisation: store match results, not faces', 'A meaningful non-biometric alternative is required'],
  },
  {
    cls: 's', letter: 'S', title: 'Social',
    plus: ['Fewer discussions about who was there', 'Trust grows when a system admits doubt'],
    minus: ['A feeling of constant surveillance', 'The teacher becomes the camera’s administrator', 'Students who are flagged more often feel excluded', 'Acceptance depends on a fair fallback'],
  },
  {
    cls: 't', letter: 'T', title: 'Technological',
    plus: ['Fast, automatic registration for most students', 'Confidence scores make uncertainty visible and measurable'],
    minus: ['False recognition (masks, glasses, lighting)', 'Camera failure (camera 2 offline)', 'The biometric database is a high-value security target', 'A fallback only works if the process around it works'],
  },
];

/* ---------- Final reflection ---------- */
const REFLECTION = {
  keep: {
    title: 'What should remain',
    items: ['Automatic registration of confident matches', 'Visible “Uncertain – Review required” status', 'Manual correction by a human', 'Short retention of biometric data'],
  },
  change: {
    title: 'What should change',
    items: ['Unresolved cases get an organisational owner, not just the teacher', 'Review window after class, not during it', 'A clear escalation and fallback process with deadlines', 'No AI hints like “likely not present”'],
  },
  cond: {
    title: 'Conditions for responsible use',
    items: ['Uncertainty never automatically becomes absence', 'Meaningful human verification, not one-click approval', 'Strict purpose limitation: attendance only', 'Minimal biometric storage, deleted quickly', 'A clear non-biometric alternative for every student', 'Monitoring of error rates per group, plus governance'],
  },
};

const REDESIGN_FLOW = [
  { cls: 's-ok', title: 'Confident match', text: 'Present / Late registered automatically' },
  { cls: 's-unc', title: 'Not confident', text: 'Uncertain, visible; attendance % frozen' },
  { cls: '', title: 'Teacher window', text: 'Optional review up to 1 hour after class' },
  { cls: '', title: 'Education Office', text: 'Case owner resolves within 48 hours' },
  { cls: '', title: 'Student', text: 'Notified, with an alternative check-in' },
  { cls: 's-ok', title: 'Verified status', text: 'Only a human decision changes the record' },
];

const FINAL_ANSWER =
  'Human control only counts when someone has the time, the information and the mandate to use it.';


/* ==========================================================
   2. SIMULATION LOGIC
   The roster is fully DERIVED from the choices. That keeps
   Back/Restart simple: change a choice, everything recomputes.
   ========================================================== */

const state = {
  step: 0,
  choices: {},        // e.g. { s1: 'B', s2: 'C', ... }
};

/* Build one student's status object. */
function S(status, time = '', note = '', tag = '') {
  return { status, time, note, tag };
}

/* Roster at a given stage (1–5), using the choices made so far. */
function rosterAt(stageNo, c) {
  const R = {
    aylin: S('present', '09:02'),
    bram:  S('present', '09:03'),
    finn:  S('present', '09:04'),
    chloe: S('present', '09:05'),
    yara:  S('present', '09:06'),
    thijs: S('absent', '—', 'Reported sick · 08:31'),
    emma:  stageNo >= 2 ? S('late', '09:14') : S('pending'),
    zoe:   stageNo >= 2 ? S('late', '09:17') : S('pending'),
    milan: S('uncertain', '09:07', 'Hood + new glasses · match 41%'),
    sara:  stageNo >= 2 ? S('uncertain', '09:21', 'Face mask · match 81%') : S('pending'),
    daan:  stageNo >= 2 ? S('uncertain', '09:23', 'Low light, back door · match 78%') : S('pending'),
    noor:  stageNo >= 3 ? S('uncertain', '?', 'Camera 2 offline at entry · time unknown') : S('pending'),
  };

  // Stage 1 — review Milan immediately
  if (c.s1 === 'A') R.milan = S('present', '09:07', 'Verified by teacher · 09:09', 'verified');

  // Stage 2 — growing queue
  if (stageNo >= 2 && c.s2) {
    const open = ['milan', 'sara', 'daan'].filter((id) => R[id].status === 'uncertain');
    if (c.s2 === 'A') {
      open.forEach((id) => { R[id] = S('present', R[id].time, 'Verified by teacher · 09:31', 'verified'); });
    }
    if (c.s2 === 'C') {
      R.sara = S('present', '09:21', 'AI suggestion accepted · 1 click', 'ai');
      R.daan = S('present', '09:23', 'AI suggestion accepted · 1 click', 'ai');
      if (R.milan.status === 'uncertain') R.milan.note = 'AI hint: “likely not present” · 41%';
    }
  }

  // Stage 3 — deadline
  if (stageNo >= 3 && c.s3) {
    const open = Object.keys(R).filter((id) => R[id].status === 'uncertain');
    open.forEach((id) => {
      if (c.s3 === 'A') {
        R[id] = id === 'noor'
          ? S('uncertain', '?', 'Reviewed · arrival time can’t be confirmed')
          : S('present', R[id].time, 'Verified by teacher · 10:29', 'verified');
      }
      if (c.s3 === 'B') R[id] = S('uncertain', R[id].time, 'Sent as Uncertain · 10:30');
      if (c.s3 === 'C') R[id] = S('absent', R[id].time, 'Auto-absent · not verified', 'auto');
    });
  }
  return R;
}

const first = (id) => STUDENTS[id].name.split(' ')[0];

function listNames(ids) {
  const n = ids.map(first);
  if (n.length <= 1) return n.join('');
  return `${n.slice(0, -1).join(', ')} and ${n[n.length - 1]}`;
}

const milanOpenAfterS1 = (c) => c.s1 !== 'A';
const stage2OpenCount = (c) => 2 + (milanOpenAfterS1(c) ? 1 : 0);

/* Uncertain students at the start of stage 3 (before the stage-3 choice). */
function openBeforeS3(c) {
  const R = rosterAt(3, { s1: c.s1, s2: c.s2 });
  return Object.keys(R).filter((id) => R[id].status === 'uncertain');
}

const isAbsentPath = (c) => c.s3 === 'C';

/* The student the consequences focus on: Milan if still unresolved, else Noor. */
function focusId(c) {
  const R = rosterAt(4, c);
  return R.milan.status === 'present' ? 'noor' : 'milan';
}

/* Stage 4 — the three impact cards (USER / SYSTEM / ORGANISATION). */
function impactCards(c) {
  const R = rosterAt(4, c);
  const f = focusId(c);
  const F = first(f);
  const pct = STUDENTS[f].attendance;
  const unresolved = Object.keys(R).filter((id) => R[id].status === 'uncertain' || R[id].tag === 'auto');
  const n = unresolved.length;
  const rushed = c.s3 === 'A' && openBeforeS3(c).filter((id) => id !== 'noor').length >= 3;

  const teacherLine = rushed
    ? 'Teacher: the lesson ended in a rush of clicking.'
    : c.s2 === 'A'
      ? 'Teacher: lost teaching time, but feels in control.'
      : 'Teacher: the lesson ended on time.';

  if (isAbsentPath(c)) {
    const after = pct - ABSENCE_PENALTY;
    return {
      user: {
        pct: `<div class="pct"><b class="down">${pct}% → ${after}%</b><small>${F}’s attendance · threshold ${ATTENDANCE_THRESHOLD}%</small></div>`,
        points: [
          ['minus', `${F} is marked Absent, but was in the room.`],
          ['minus', `An automatic warning email is sent. ${F} has to dispute it.`],
          ['minus', `${teacherLine} You didn’t realise anything was wrong.`],
        ],
      },
      system: {
        points: [
          ['minus', 'The record is complete, and wrong.'],
          ['minus', 'The doubt (41% match, camera outage) is erased from the official record.'],
          ['minus', 'The error spreads to study progress, study advice and grant reporting.'],
          ...(c.s2 === 'C' ? [['minus', 'Sara and Daan: AI suggestions logged as “human verified”.']] : []),
        ],
      },
      org: {
        points: [
          ['minus', 'The Education Office sees a clean list, so no problem is visible.'],
          ['minus', `A complaint arrives 4 days later. ${F} carries the burden of proof.`],
          ['info', 'Who decided: the AI, the teacher or the process?'],
        ],
      },
    };
  }

  return {
    user: {
      pct: `<div class="pct"><b class="same">${pct}% → ${pct}%</b><small>${F}’s attendance · unchanged</small></div>`,
      points: [
        ['plus', `${F} gets a notification: “Your registration could not be verified. Please respond within 5 days.”`],
        ['plus', 'Nothing is decided yet, and the student can respond.'],
        ['info', teacherLine],
      ],
    },
    system: {
      points: [
        ['plus', `${n} registration${n === 1 ? '' : 's'} sent as Uncertain. The doubt stays visible.`],
        ['plus', 'No biometric doubt was turned into an official status.'],
        ...(c.s2 === 'C' ? [['minus', 'Sara and Daan: AI suggestions logged as “human verified”.']] : []),
        ...(rushed ? [['minus', 'Several reviews in under a minute: verification on paper only.']] : []),
        ['minus', 'Camera 2 outage: the hardware creates human work.'],
      ],
    },
    org: {
      points: [
        ['plus', `The Education Office receives ${n} open case${n === 1 ? '' : 's'} and can investigate.`],
        ['minus', 'There is no clear case owner and no deadline yet.'],
        ['info', 'Across the faculty: ~340 uncertain cases a week.'],
      ],
    },
  };
}


/* ==========================================================
   3. RENDERING
   ========================================================== */

const $ = (sel) => document.querySelector(sel);
const stageEl = $('#stage');
const val = (v, c) => (typeof v === 'function' ? v(c) : v);

let lastRosterStatus = null;   // for flashing rows whose status changed
let lastToastStep = null;      // so toasts only fire on entering a step
let countdownTimer = null;
let countdownEnd = 0;

const ICONS = {
  user: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/></svg>',
  system: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/></svg>',
  org: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18M5 21V9l7-5 7 5v12M9 21v-6h6v6"/></svg>',
  warn: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 2 20h20L12 3z"/><path d="M12 10v4M12 17.5v.5"/></svg>',
};

function render() {
  const step = STEPS[state.step];
  const c = state.choices;
  clearInterval(countdownTimer);

  // Header, progress, timeline
  $('#clock').textContent = step.clock;
  $('#progressLabel').textContent = step.progress;
  renderTimeline();

  // Main content
  let html = '';
  if (step.type === 'intro') html = renderIntro();
  if (step.type === 'stage') html = renderStage(step, c);
  if (step.type === 'boundary') html = renderBoundary(c);
  if (step.type === 'elsa') html = renderElsa();
  if (step.type === 'reflection') html = renderReflection(c);
  stageEl.innerHTML = html;

  // Countdown for the deadline stage
  if (step.countdown && !c[step.id]) startCountdown();
  else if (step.countdown) markCountdownDone();

  // Toasts only when a step is entered
  if (lastToastStep !== step.id) {
    lastToastStep = step.id;
    $('#toasts').innerHTML = '';
    (step.toasts || []).forEach((t, i) => setTimeout(() => toast(t), 450 + i * 700));
  }

  updateControls();
}

function renderTimeline() {
  $('#timeline').innerHTML = STEPS.map((s, i) => {
    const cls = i < state.step ? 'done' : i === state.step ? 'current' : '';
    return `<li class="tl-item ${cls}"><span class="tl-dot"></span><span class="tl-time">${s.tlTime}</span><span class="tl-name">${s.tlName}</span></li>`;
  }).join('');
}

/* ---------- Briefing ---------- */
function renderIntro() {
  const legend = ['present', 'late', 'absent', 'uncertain'].map((s) => `
    <div class="legend-item"><span>${s === 'uncertain' ? `<span class="status uncertain">Uncertain</span>${REVIEW_BADGE}` : `<span class="status ${s}">${STATUS_LABELS[s]}</span>`}</span><span>${{
      present: 'Recognised on time',
      late: 'Recognised after start',
      absent: 'Confirmed not present',
      uncertain: 'AI is not sure. A human must check.',
    }[s]}</span></div>`).join('');

  return `
    <div class="layout layout-wide">
      <section class="panel report">
        <h1>What happens when human control exists,<br>but nobody has time to use it?</h1>
        <p class="lead">It’s 2045. At this university, <b>PresenceAI</b> registers attendance automatically with facial recognition as students walk into the classroom.</p>
        <div class="intro-grid">
          <div class="facts">
            <div class="fact"><span class="fact-num">1</span><span>Recognised students are registered as <b>Present</b> or <b>Late</b> automatically.</span></div>
            <div class="fact"><span class="fact-num">2</span><span>If the AI isn’t sure, it shows <b>Uncertain – Review required</b>. It must never mark the student absent by itself.</span></div>
            <div class="fact"><span class="fact-num">3</span><span>At <b>10:30</b> the list is sent to the Education Office automatically. Unresolved cases stay Uncertain, and the student gets a notification.</span></div>
          </div>
          <div class="facts">
            <div class="role-card">Your role: you are the teacher of ${COURSE.group}. You teach, answer questions <i>and</i> review registrations.</div>
            <div>
              <div class="section-label">Attendance statuses</div>
              <div class="legend">${legend}</div>
            </div>
          </div>
        </div>
      </section>
    </div>`;
}

/* ---------- Stage screens ---------- */
function renderStage(step, c) {
  const chosen = c[step.id];
  const aside = step.aside === 'roster' ? renderRoster(step.stageNo, c)
    : step.aside === 'kpi' ? renderKpis(c) : '';

  const choicesHtml = step.choices.map((ch) => `
    <button class="choice ${chosen === ch.key ? 'selected' : ''} ${chosen && chosen !== ch.key ? 'dimmed' : ''}"
            data-key="${ch.key}" ${chosen ? 'disabled' : ''}>
      <span class="choice-key">${ch.key}</span>
      <span class="choice-body">
        <strong>${ch.label}</strong>
        <span>${val(ch.detail, c)}</span>
        ${ch.warn && !chosen ? `<span class="choice-tag">${ch.warn}</span>` : ''}
      </span>
    </button>`).join('');

  const consequence = chosen ? renderConsequence(step.choices.find((ch) => ch.key === chosen).consequence(c)) : '';

  // Stage 4 uses the full width for the three impact cards
  if (step.aside === 'none') {
    const imp = step.impacts(c);
    return `
      <div class="layout layout-wide">
        <section class="panel wide-card">
          <span class="kicker ${step.kickerClass || ''}">${step.kicker}</span>
          <h1 style="font-size:1.75rem">${val(step.title, c)}</h1>
          <div class="impact-grid">
            ${impactCard('user', 'USER', 'Teacher & student', imp.user)}
            ${impactCard('system', 'SYSTEM', 'AI, uncertainty & data', imp.system)}
            ${impactCard('org', 'ORGANISATION', 'Administration & policy', imp.org)}
          </div>
          <p class="question">${val(step.question, c)}</p>
          <div class="choices ${chosen ? '' : 'horizontal'}">${choicesHtml}</div>
          ${consequence}
        </section>
      </div>`;
  }

  return `
    <div class="layout layout-split">
      ${aside}
      <section class="panel incident">
        <span class="kicker ${step.kickerClass || ''}">${step.kicker}</span>
        <h1>${val(step.title, c)}</h1>
        ${step.countdown ? '<div class="countdown" id="countdown">List sends in <b id="countdownValue">02:00</b></div>' : ''}
        <div class="situation">${val(step.situation, c)}</div>
        <p class="question">${val(step.question, c)}</p>
        <div class="choices">${choicesHtml}</div>
        ${consequence}
      </section>
    </div>`;
}

function impactCard(cls, title, sub, data) {
  return `
    <article class="impact ${cls}">
      <div class="impact-head">${ICONS[cls]}<div><h3>${title}</h3><p>${sub}</p></div></div>
      ${data.pct || ''}
      <ul class="points">${data.points.map(([t, x]) => `<li class="pt ${t}">${x}</li>`).join('')}</ul>
    </article>`;
}

function renderConsequence(cons) {
  return `
    <section class="consequence ${cons.tone ? 'tone-' + cons.tone : ''}" id="consequence">
      ${cons.boundary ? `
        <div class="boundary-banner">${ICONS.warn}
          <div><strong>MORAL BOUNDARY CROSSED</strong>
          <span>Uncertain biometric recognition now becomes an official negative status, without verification.</span></div>
        </div>` : ''}
      <span class="kicker k-result">Consequence</span>
      <h3>${cons.title}</h3>
      <ul class="points">${cons.points.map(([t, x]) => `<li class="pt ${t}">${x}</li>`).join('')}</ul>
    </section>`;
}

/* ---------- Attendance roster (left panel) ---------- */
function renderRoster(stageNo, c) {
  const R = rosterAt(stageNo, c);
  const order = { uncertain: 0, absent: 1, late: 2, present: 3, pending: 4 };
  const ids = Object.keys(R).sort((a, b) =>
    order[R[a].status] - order[R[b].status] || STUDENTS[a].name.localeCompare(STUDENTS[b].name));

  const count = (s) => ids.filter((id) => R[id].status === s).length;
  const prev = lastRosterStatus || {};
  const prevCounts = prev.__counts || {};
  const counts = { present: count('present'), late: count('late'), absent: count('absent'), uncertain: count('uncertain') };

  const rows = ids.map((id) => {
    const r = R[id];
    const changed = lastRosterStatus && prev[id] && prev[id] !== r.status;
    const initials = STUDENTS[id].name.split(' ').map((w) => w[0]).filter((ch) => ch === ch.toUpperCase()).slice(0, 2).join('');
    const tagCls = r.tag ? `tag-${r.tag}` : '';
    return `
      <div class="row ${r.status === 'uncertain' ? 'is-uncertain' : ''} ${changed ? 'flash' : ''}">
        <span class="avatar">${initials}</span>
        <span class="row-main"><strong>${STUDENTS[id].name}</strong>
          <span class="row-note ${tagCls}">${r.time && r.time !== '—' ? r.time + ' · ' : ''}${r.note || (r.status === 'pending' ? 'Waiting for camera match' : 'Recognised automatically')}</span>
        </span>
        <span class="status-cell">${r.status === 'uncertain'
          ? `<span class="status uncertain">Uncertain</span>${REVIEW_BADGE}`
          : `<span class="status ${r.status}">${STATUS_LABELS[r.status]}</span>`}</span>
      </div>`;
  }).join('');

  // remember for next render
  lastRosterStatus = Object.fromEntries(ids.map((id) => [id, R[id].status]));
  lastRosterStatus.__counts = counts;

  const counter = (k, label) =>
    `<div class="counter ${k} ${prevCounts[k] !== undefined && prevCounts[k] !== counts[k] ? 'bump' : ''}"><b>${counts[k]}</b><span>${label}</span></div>`;

  const sent = stageNo >= 3 && c.s3;
  return `
    <aside class="panel attendance">
      <div class="panel-head">
        <div><h2>Live attendance</h2><div class="sub">${COURSE.group} · ${Object.keys(R).length} students</div></div>
        <span class="live-dot ${sent ? 'sent-badge' : ''}">${sent ? 'Sent 10:30' : 'Live'}</span>
      </div>
      <div class="counters">
        ${counter('present', 'Present')}${counter('late', 'Late')}${counter('uncertain', 'Uncertain')}${counter('absent', 'Absent')}
      </div>
      <div class="roster">${rows}</div>
    </aside>`;
}

/* ---------- Faculty KPIs (stage 5 left panel) ---------- */
function renderKpis(c) {
  return `
    <aside class="panel attendance">
      <div class="panel-head">
        <div><h2>Faculty overview</h2><div class="sub">Week 12 · all programmes</div></div>
        <span class="live-dot">Live</span>
      </div>
      <div class="kpis">
        <div class="kpi"><span>Classrooms using PresenceAI</span><b>120</b></div>
        <div class="kpi"><span>Registrations this week</span><b>18,400</b></div>
        <div class="kpi purple"><span>Uncertain this week</span><b>340</b></div>
        <div class="kpi alert"><span>Resolved within 5 days</span><b>41%</b><div class="bar"><i style="width:41%"></i></div></div>
        <div class="kpi"><span>Uncertain rate by camera / student group</span><b>1.1% – 4.6%</b></div>
        ${isAbsentPath(c) ? '<div class="kpi alert"><span>Attendance disputes this week</span><b>27</b></div>' : ''}
      </div>
    </aside>`;
}

/* ---------- Moral boundary ---------- */
function renderBoundary(c) {
  const policy = c.s5 === 'A';
  const inClass = c.s3 === 'C';
  let verdict;
  if (policy && inClass) {
    verdict = ['v-crossed', '!', 'Boundary crossed twice', 'First in class under time pressure, then as official policy for everyone.'];
  } else if (policy) {
    verdict = ['v-crossed', '!', 'Boundary crossed at policy level', 'In class you protected the students. As policy, you removed that protection for everyone.'];
  } else if (inClass) {
    verdict = ['v-drift', '!', 'Boundary crossed in class, under pressure', 'You rejected automatic absence as policy, but did it yourself at 10:28. Pressure makes people drift.'];
  } else {
    verdict = ['v-kept', '✓', 'Boundary respected on your whole path', 'Uncertainty never became an official negative decision.'];
  }

  const card = (e, accent) => `
    <article class="card accent" style="--c:${accent}">
      <h3>${e.title}</h3>
      <ul class="points">${e.points.map((p) => `<li class="pt info" style="font-weight:400">${p}</li>`).join('')}</ul>
    </article>`;

  return `
    <div class="layout layout-wide">
      <section class="panel report">
        <span class="kicker k-result">Moral boundary</span>
        <div class="boundary-statement">“${MORAL_BOUNDARY}”</div>
        <div class="verdict ${verdict[0]}"><span class="v-icon">${verdict[1]}</span><div><b>${verdict[2]}</b>${verdict[3]}</div></div>
        <div class="two-col">
          ${card(ETHICS.duty, 'var(--user)')}
          ${card(ETHICS.consequences, 'var(--system)')}
        </div>
      </section>
    </div>`;
}

/* ---------- ELSA ---------- */
function renderElsa() {
  const col = (e) => `
    <article class="card elsa-col ${e.cls}">
      <div class="elsa-letter"><i>${e.letter}</i>${e.title}</div>
      <div class="elsa-sub">Positive</div>
      <ul class="points">${e.plus.map((x) => `<li class="pt plus">${x}</li>`).join('')}</ul>
      <div class="elsa-sub">Negative</div>
      <ul class="points">${e.minus.map((x) => `<li class="pt minus">${x}</li>`).join('')}</ul>
    </article>`;

  return `
    <div class="layout layout-wide">
      <section class="panel report">
        <span class="kicker k-result">ELSA analysis</span>
        <h1>Ethical · Legal · Social · Technological impact</h1>
        <div class="four-col">${ELSA.map(col).join('')}</div>
      </section>
    </div>`;
}

/* ---------- Final reflection ---------- */
function renderReflection(c) {
  const col = (key, icon) => {
    const r = REFLECTION[key];
    return `
      <article class="card accent reflect-col ${key}">
        <h3>${icon} ${r.title}</h3>
        <ul>${r.items.map((x) => `<li>${x}</li>`).join('')}</ul>
      </article>`;
  };

  const flow = REDESIGN_FLOW.map((f, i) => `
    ${i ? '<span class="flow-arrow">→</span>' : ''}
    <div class="flow-step ${f.cls}"><b>${f.title}</b>${f.text}</div>`).join('');

  const path = Object.keys(PATH_LABELS).map((k, i) => {
    const risky = RISKY_CHOICES[k] && RISKY_CHOICES[k] === c[k];
    return `<span class="path-chip ${risky ? 'risk' : ''}"><b>${i + 1}${c[k] || '–'}</b> ${PATH_LABELS[k][c[k]] || 'Not chosen'}</span>`;
  }).join('');

  return `
    <div class="layout layout-wide">
      <section class="panel report compact">
        <span class="kicker k-result">Final reflection</span>
        <div class="three-col">
          ${col('keep', '✓')}
          ${col('change', '↻')}
          ${col('cond', '§')}
        </div>
        <div>
          <div class="section-label">Recommended redesign</div>
          <div class="flow">${flow}</div>
        </div>
        <div class="never">✕ Never: <s>Uncertain → Absent automatically</s></div>
        <div>
          <div class="section-label">Your path</div>
          <div class="path">${path}</div>
        </div>
        <div class="final-answer"><span>${FINAL_ANSWER}</span><button class="btn" data-action="restart">Restart simulation</button></div>
      </section>
    </div>`;
}

/* ---------- Toasts ---------- */
function toast({ tone, title, text }) {
  const el = document.createElement('div');
  el.className = `toast t-${tone}`;
  el.innerHTML = `<div><b>${title}</b><span>${text}</span></div>`;
  const box = $('#toasts');
  box.appendChild(el);
  while (box.children.length > 2) box.firstElementChild.remove();   // max 2 visible
  setTimeout(() => el.classList.add('out'), 4000);
  setTimeout(() => el.remove(), 4400);
}

/* ---------- Countdown (stage 3) ---------- */
function startCountdown() {
  const step = STEPS[state.step];
  if (!countdownEnd) countdownEnd = Date.now() + step.countdown * 1000;
  const tick = () => {
    const el = $('#countdownValue');
    if (!el) return clearInterval(countdownTimer);
    const left = Math.max(0, Math.round((countdownEnd - Date.now()) / 1000));
    el.textContent = `${String(Math.floor(left / 60)).padStart(2, '0')}:${String(left % 60).padStart(2, '0')}`;
    $('#clock').textContent = left > 60 ? '10:28' : left > 0 ? '10:29' : '10:30';
    if (left === 0) {
      $('#countdown').classList.add('expired');
      $('#countdown').innerHTML = 'Deadline reached. <b>Waiting for your decision</b>';
      clearInterval(countdownTimer);
    }
  };
  tick();
  countdownTimer = setInterval(tick, 1000);
}
function markCountdownDone() {
  const el = $('#countdown');
  if (el) el.innerHTML = 'Decision made · list sent at <b>10:30</b>';
  $('#clock').textContent = '10:30';
}


/* ==========================================================
   4. CONTROLS
   ========================================================== */

function currentStep() { return STEPS[state.step]; }
function needsChoice(step) { return step.type === 'stage' && !state.choices[step.id]; }

/* Clear a stage's choice and all later ones (they depend on it). */
function clearFrom(stageNo) {
  STEPS.forEach((s) => { if (s.stageNo >= stageNo) delete state.choices[s.id]; });
}

function choose(key) {
  const step = currentStep();
  if (step.type !== 'stage' || state.choices[step.id]) return;
  if (!step.choices.some((ch) => ch.key === key)) return;
  clearFrom(step.stageNo);
  state.choices[step.id] = key;
  render();
  const cons = $('#consequence');
  if (cons) cons.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function goNext() {
  const step = currentStep();
  if (needsChoice(step) || state.step >= STEPS.length - 1) return;   // gate: no skipping
  state.step++;
  countdownEnd = 0;
  render();
  stageEl.scrollTop = 0;
}

function goBack() {
  const step = currentStep();
  // First undo the choice on this stage, then move to the previous screen
  if (step.type === 'stage' && state.choices[step.id]) {
    clearFrom(step.stageNo);
    countdownEnd = 0;
    render();
    return;
  }
  if (state.step === 0) return;
  state.step--;
  countdownEnd = 0;
  render();
}

function restart() {
  closeModal();
  state.step = 0;
  state.choices = {};
  lastRosterStatus = null;
  lastToastStep = null;
  countdownEnd = 0;
  $('#toasts').innerHTML = '';
  render();
}

function updateControls() {
  const step = currentStep();
  const btnNext = $('#btnContinue');
  const locked = needsChoice(step);
  const last = state.step === STEPS.length - 1;

  btnNext.disabled = locked || last;
  btnNext.style.visibility = last ? 'hidden' : 'visible';
  btnNext.textContent = step.type === 'intro' ? 'Start simulation →' : 'Continue →';
  btnNext.classList.toggle('ready', !locked && step.type === 'stage');
  $('#btnBack').disabled = state.step === 0;

  const keys = step.type === 'stage' ? step.choices.map((ch) => `<kbd>${ch.key}</kbd>`).join(' ') : '';
  $('#hint').innerHTML = locked
    ? `Choose an action to continue · ${keys}`
    : last
      ? 'End of simulation'
      : 'Press <kbd>→</kbd> or <kbd>Enter</kbd> to continue · <kbd>F</kbd> fullscreen';
}

/* ---------- Modal ---------- */
function openModal() { $('#modal').hidden = false; $('#btnConfirmRestart').focus(); }
function closeModal() { $('#modal').hidden = true; }
const modalOpen = () => !$('#modal').hidden;

/* ---------- Fullscreen ---------- */
function toggleFullscreen() {
  if (!document.fullscreenElement) document.documentElement.requestFullscreen?.().catch(() => {});
  else document.exitFullscreen?.();
}

/* ---------- Event wiring ---------- */
$('#btnContinue').addEventListener('click', goNext);
$('#btnBack').addEventListener('click', goBack);
$('#btnRestart').addEventListener('click', openModal);
$('#btnCancelRestart').addEventListener('click', closeModal);
$('#btnConfirmRestart').addEventListener('click', restart);
$('#btnFullscreen').addEventListener('click', toggleFullscreen);
$('#modal').addEventListener('click', (e) => { if (e.target.id === 'modal') closeModal(); });

stageEl.addEventListener('click', (e) => {
  const choiceBtn = e.target.closest('.choice');
  if (choiceBtn && !choiceBtn.disabled) choose(choiceBtn.dataset.key);
  if (e.target.closest('[data-action="restart"]')) openModal();
});

document.addEventListener('keydown', (e) => {
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  if (modalOpen()) {
    if (e.key === 'Escape') closeModal();
    return;
  }
  const k = e.key.toUpperCase();
  if (['A', 'B', 'C'].includes(k)) choose(k);
  else if (['1', '2', '3'].includes(k)) choose('ABC'[Number(k) - 1]);
  else if (e.key === 'ArrowRight' || e.key === 'Enter') { e.preventDefault(); goNext(); }
  else if (e.key === 'ArrowLeft') goBack();
  else if (k === 'F') toggleFullscreen();
});

/* ---------- Init ---------- */
$('#courseInfo').innerHTML = [COURSE.name, COURSE.group, COURSE.room, COURSE.date].map((x) => `<span>${x}</span>`).join('');
render();
