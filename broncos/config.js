// Shared-database settings. See README.md for the 5-minute setup.
//
// Until `firebase` is filled in, the app runs in "this device only" mode:
// everything works, but nothing is shared between people.

export const config = {
  // Paste the web-app config object from the Firebase console here, e.g.
  // firebase: {
  //   apiKey: "AIza...",
  //   authDomain: "broncos-tix.firebaseapp.com",
  //   projectId: "broncos-tix",
  //   storageBucket: "broncos-tix.firebasestorage.app",
  //   messagingSenderId: "1234567890",
  //   appId: "1:1234567890:web:abcdef",
  // },
  firebase: null,

  // Firestore document that holds this season. Change it to start a fresh
  // season (e.g. 'season-2027') without losing the old one.
  seasonDocId: 'season-2026',
};
