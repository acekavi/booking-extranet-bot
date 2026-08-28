/**
 * Every selector in one place.
 *
 * Extranets get redesigned without notice, so when this tool breaks it is
 * almost always this file that needs editing -- and only this file. Run
 * `npm run verify-selectors` to find out which entry has gone stale.
 */
export const CALENDAR_URL =
  "https://admin.booking.com/hotel/hoteladmin/extranet_ng/manage/calendar/index.html?source=nav";

export const LOGIN_URL = "https://admin.booking.com/hotel/hoteladmin/";

export function roomPanel(roomId: string): string {
  return `[data-test-id="room-${roomId}"]`;
}

export const bulkEdit = {
  /** Matches real room panels; the room filter dropdown shares the prefix. */
  anyRoomPanel: '[data-test-id^="room-"]',
  openButtonName: "Bulk edit",
  dateFrom: "#date-from",
  dateUntil: "#date-until",
  /** Static text used only as a safe click target to dismiss the datepicker. */
  weekdayLabelText: "Which days of the week do you want to apply changes to?",
  roomsToSellToggle: /Rooms to Sell/,
  pricesToggle: /^Prices/,
  roomsToSellInput: "#single-rts-input",
  priceSelect: (index: number) => `#price-select-${index}`,
  priceInput: (index: number) => `#price-input-${index}`,
  anyPriceInput: '[id^="price-input-"]',
  /** Both Prices and Restrictions render one; take the first. */
  addEntry: '[data-test-id="add-entry"]',
  saveButtonName: "Save changes",
  saveSuccessText: "Your changes were successfully saved!",
  closeButton: '[data-test-id="close-button"]',
  modalFader: '[data-test-id="fader"].av-cal-list-general-modal__fader--open',
};
