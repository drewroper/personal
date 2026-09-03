// First-run data. Used once, the first time the database is empty. After
// that, people are managed in the app.
export const SEED = {
  people: {
    drew:  { name: 'Drew',  color: '#FFB000', order: 1, defaultHolder: true  },
    megan: { name: 'Megan', color: '#FF6FA5', order: 2, defaultHolder: true  },
    mikey: { name: 'Mikey', color: '#5AB4FF', order: 3, defaultHolder: false },
    mason: { name: 'Mason', color: '#7EE787', order: 4, defaultHolder: false },
    jenny: { name: 'Jenny', color: '#C792EA', order: 5, defaultHolder: false },
  },
  // gameId -> personId. Mason already has the Raiders game.
  claims: { wk11: 'mason' },
  // gameId -> { personId: true }
  unavailable: {},
  // gameId -> free text
  notes: {},
};
