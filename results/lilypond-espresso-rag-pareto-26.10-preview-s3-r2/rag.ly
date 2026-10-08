\version "2.24.0"

\header {
  title = "Espresso Rag"
  subtitle = "a café piano novelty"
}

% ============================================================
% RIGHT HAND  (temporarily moves to the lower staff, bars 9-12,
% while the left hand crosses over it on the upper staff)
% ============================================================
upper = {
  \key c \major
  \time 2/4
  \tempo "Light ragtime (straight eighths)" 4 = 104
  % ---- A section (bars 1-8): melody in the right hand ----
  % bars 1-4
  c''8 e''16 g''~ g''8 e''8 |
  r16 e'' g'' e''~ e''8 bes'16 g' |
  a'8 c''16 d''~ d''8 c''16 a' |
  a'16 f'16 g'8 f'8 r8 |
  \break
  % bars 5-8
  e''8 g''16 a''~ a''8 g''16 e'' |
  cis''8 e''16 g''~ g''8 e''16 cis'' |
  f''16 d'' f'' a''~ a''8 f''8 |
  e''8 g''16 bes''16 g''8 e''8 |
  \break
  % ---- bars 9-12: R.H. takes over the oom-pah bass ----
  \change Staff = "lower"
  f,8_\markup \italic "R.H." <f a>8 c,8 <f a>8 |
  bes,8 <d f>8 f,8 <d f>8 |
  c,8 <g bes>8 c,8 <g bes>8 |
  g,8 <f b>8 d,8 <f b>8 |
  \break
  \change Staff = "upper"
  % ---- A' section (bars 13-16): back to normal hands ----
  c'''8^\markup \italic "R.H. — normal hands" g''16 e''16 c''8 g'8 |
  a'8 cis''16 e''~ e''8 a''16 cis'' |
  f''8 d''16 f''16 b'8 d''16 f''16 |
  r8 g''16 a''16 <c'' e'' g'' c'''>4\fermata |
  \bar "|."
}

% ============================================================
% LEFT HAND  (crosses over the right hand, bars 9-12: it is
% written on the upper staff, above the right-hand bass)
% ============================================================
lower = {
  \key c \major
  \time 2/4
  \clef bass
  % bars 1-4
  c,8\p <e g>8 g,8 <e g>8 |
  c,8 <e g>8 bes,8 <e g>8 |
  f,8 <f a>8 c,8 <f a>8 |
  f,8 <f a>8 c,8 <f a>8 |
  % bars 5-8
  c,8 <e g>8 g,8 <e g>8 |
  a,8 <g cis'>8 e,8 <g cis'>8 |
  d,8\< <f a>8 a,8 <f a>8 |
  c,8 <e bes>8 g,8 <e bes>8\! |
  % ---- bars 9-12: L.H. crosses over, playing the tune up high ----
  \change Staff = "upper"
  a'8\mf^\markup \bold \italic "L.H. over R.H. (bars 9–12)" c''16 d''~ d''8 c''16 a' |
  d''8 f''16 d''~ d''8 bes'8 |
  g'8 bes'16 c''~ c''8 bes'16 g' |
  f''16 d'' b' d''~ d''8 f''8 |
  \change Staff = "lower"
  % bars 13-16
  c,8\p_\markup \italic "L.H." <e g>8 g,8 <e g>8 |
  a,8 <g cis'>8 e,8 <g cis'>8 |
  d,8 <f a>8 g,8 <f b>8 |
  c,8 <e g>8 <c e g c'>4\fermata |
  \bar "|."
}

\paper {
  system-system-spacing.basic-distance = #22
  print-page-number = ##f
}

\score {
  \new PianoStaff \with { instrumentName = "Piano" }
  <<
    \new Staff = "upper" \upper
    \new Staff = "lower" \lower
  >>
  \layout { }
}
