import { isBoardData, moveCard, type Column } from "@/lib/kanban";

describe("moveCard", () => {
  const baseColumns: Column[] = [
    { id: "col-a", title: "A", cardIds: ["card-1", "card-2"] },
    { id: "col-b", title: "B", cardIds: ["card-3"] },
  ];

  it("reorders cards in the same column", () => {
    const result = moveCard(baseColumns, "card-2", "card-1");
    expect(result[0].cardIds).toEqual(["card-2", "card-1"]);
  });

  it("moves cards to another column", () => {
    const result = moveCard(baseColumns, "card-2", "card-3");
    expect(result[0].cardIds).toEqual(["card-1"]);
    expect(result[1].cardIds).toEqual(["card-2", "card-3"]);
  });

  it("drops cards to the end of a column", () => {
    const result = moveCard(baseColumns, "card-1", "col-b");
    expect(result[0].cardIds).toEqual(["card-2"]);
    expect(result[1].cardIds).toEqual(["card-3", "card-1"]);
  });
});

describe("isBoardData", () => {
  it("accepts valid board payloads", () => {
    expect(
      isBoardData({
        columns: [{ id: "col-1", title: "Todo", cardIds: ["card-1"] }],
        cards: {
          "card-1": { id: "card-1", title: "Task", details: "Details" },
        },
      })
    ).toBe(true);
  });

  it("rejects invalid board payloads", () => {
    expect(isBoardData({ columns: [{ id: "col-1", title: "Todo", cardIds: ["missing"] }], cards: {} })).toBe(
      false
    );
    expect(isBoardData({ columns: [] })).toBe(false);
  });
});
